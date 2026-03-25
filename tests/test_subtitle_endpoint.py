"""Tests for non-blocking subtitle extraction endpoint (Phase 1).

Tests:
- Cache miss → 202 {"status": "extracting", "retry_after": 5}
- Second request while task running → 202 immediate (no double-start)
- After task completes → 200 with file bytes
- Task failed → /status returns "not_started"
- /status on cached file → "ready" (no DB query)
- /status while extracting → "extracting"
- /status before any request → "not_started"
- Invalid format → 400
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_media(streams):
    """Build a mock MediaItem with the given stream list."""
    media = MagicMock()
    media.id = 1
    media.streams = streams
    return media


def _make_stream(stream_index: int):
    from app.models.media import CodecType
    s = MagicMock()
    s.stream_index = stream_index
    s.codec_type = CodecType.SUBTITLE
    return s


def _make_session(media):
    """Async session mock that returns media from execute()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = media

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# Unit tests — get_subtitle (non-blocking path)
# ---------------------------------------------------------------------------

class TestGetSubtitleNonBlocking:
    """Test that cache-miss path returns 202 and launches background task."""

    @pytest.fixture(autouse=True)
    def clear_module_state(self, tmp_path):
        """Reset in-memory dicts and redirect cache dir for each test."""
        import app.api.v1.subtitles as mod
        mod._subtitle_tasks.clear()
        mod._subtitle_locks.clear()
        # Point cache dir at tmp so we never accidentally hit real files
        self._orig_dir = mod.SUBTITLE_CACHE_DIR
        mod.SUBTITLE_CACHE_DIR = tmp_path / "subtitles"
        mod.SUBTITLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        yield
        mod.SUBTITLE_CACHE_DIR = self._orig_dir
        mod._subtitle_tasks.clear()
        mod._subtitle_locks.clear()

    @pytest.mark.asyncio
    async def test_cache_miss_returns_202(self, tmp_path):
        import app.api.v1.subtitles as mod

        session = _make_session(_make_media([_make_stream(5)]))

        # Blocker so the background task never completes during the test
        blocker = asyncio.Event()

        async def slow_extract(*args, **kwargs):
            await blocker.wait()
            return b"[Script Info]\n"

        with patch("app.api.v1.subtitles._extract_and_cache", new=AsyncMock(side_effect=slow_extract)):
            # Patch create_task to track but still schedule
            original_create_task = asyncio.create_task
            created = []

            def fake_create_task(coro, **kw):
                t = original_create_task(coro, **kw)
                created.append(t)
                return t

            with patch("asyncio.create_task", side_effect=fake_create_task):
                resp = await mod.get_subtitle(media_id=1, session=session, track=5, format="ass")

        assert resp.status_code == 202
        body = resp.body
        import json
        data = json.loads(body)
        assert data["status"] == "extracting"
        assert data["retry_after"] == 5
        assert resp.headers["retry-after"] == "5"

        # Cleanup
        blocker.set()
        for t in created:
            try:
                await asyncio.wait_for(t, timeout=1)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_cache_hit_returns_200(self, tmp_path):
        import app.api.v1.subtitles as mod

        # Pre-populate cache
        cache_file = mod.SUBTITLE_CACHE_DIR / "1_5.ass"
        cache_file.write_bytes(b"[Script Info]\nTitle: test\n")

        session = _make_session(_make_media([_make_stream(5)]))

        resp = await mod.get_subtitle(media_id=1, session=session, track=5, format="ass")

        assert resp.status_code == 200
        assert b"[Script Info]" in resp.body

    @pytest.mark.asyncio
    async def test_second_request_while_task_running_no_double_start(self, tmp_path):
        """Two concurrent requests for the same track should start only ONE task."""
        import app.api.v1.subtitles as mod

        blocker = asyncio.Event()
        call_count = 0

        async def slow_extract(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await blocker.wait()

        with patch("app.api.v1.subtitles._extract_and_cache", new=AsyncMock(side_effect=slow_extract)):
            session1 = _make_session(_make_media([_make_stream(5)]))
            session2 = _make_session(_make_media([_make_stream(5)]))

            resp1 = await mod.get_subtitle(media_id=1, session=session1, track=5, format="ass")
            resp2 = await mod.get_subtitle(media_id=1, session=session2, track=5, format="ass")

        assert resp1.status_code == 202
        assert resp2.status_code == 202

        # Only ONE task should be in the dict
        assert len(mod._subtitle_tasks) == 1

        blocker.set()
        tasks = list(mod._subtitle_tasks.values())
        for t in tasks:
            try:
                await asyncio.wait_for(asyncio.shield(t), timeout=1)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_after_task_completes_returns_200(self, tmp_path):
        """Once background task writes cache, subsequent request returns 200."""
        import app.api.v1.subtitles as mod

        async def fast_extract(media_id, relative_index, abs_track, fmt):
            # Write the cache file directly (simulating what _extract_and_cache does)
            cache_file = mod.SUBTITLE_CACHE_DIR / f"{media_id}_{abs_track}.{fmt}"
            cache_file.write_bytes(b"[Script Info]\nTitle: cached\n")

        with patch("app.api.v1.subtitles._extract_and_cache", new=AsyncMock(side_effect=fast_extract)):
            session = _make_session(_make_media([_make_stream(5)]))
            resp1 = await mod.get_subtitle(media_id=1, session=session, track=5, format="ass")

        assert resp1.status_code == 202

        # Let the task run to completion
        key = (1, 5, "ass")
        task = mod._subtitle_tasks.get(key)
        if task:
            try:
                await asyncio.wait_for(task, timeout=2)
            except Exception:
                pass

        # Now cache should exist → 200
        session2 = _make_session(_make_media([_make_stream(5)]))
        resp2 = await mod.get_subtitle(media_id=1, session=session2, track=5, format="ass")
        assert resp2.status_code == 200
        assert b"cached" in resp2.body

    @pytest.mark.asyncio
    async def test_invalid_track_returns_400(self, tmp_path):
        import app.api.v1.subtitles as mod
        from fastapi import HTTPException

        session = _make_session(_make_media([_make_stream(3)]))

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle(media_id=1, session=session, track=99, format="ass")

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_format_returns_400(self, tmp_path):
        import app.api.v1.subtitles as mod
        from fastapi import HTTPException

        session = _make_session(_make_media([_make_stream(0)]))

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle(media_id=1, session=session, track=0, format="vtt")

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_media_not_found_returns_404(self, tmp_path):
        import app.api.v1.subtitles as mod
        from fastapi import HTTPException

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle(media_id=999, session=session, track=0, format="ass")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Unit tests — /status endpoint
# ---------------------------------------------------------------------------

class TestGetSubtitleStatus:
    """Test the /status polling endpoint."""

    @pytest.fixture(autouse=True)
    def clear_module_state(self, tmp_path):
        import app.api.v1.subtitles as mod
        mod._subtitle_tasks.clear()
        mod._subtitle_locks.clear()
        self._orig_dir = mod.SUBTITLE_CACHE_DIR
        mod.SUBTITLE_CACHE_DIR = tmp_path / "subtitles"
        mod.SUBTITLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        yield
        mod.SUBTITLE_CACHE_DIR = self._orig_dir
        mod._subtitle_tasks.clear()
        mod._subtitle_locks.clear()

    @pytest.mark.asyncio
    async def test_status_ready_when_cached(self, tmp_path):
        import app.api.v1.subtitles as mod

        (mod.SUBTITLE_CACHE_DIR / "1_5.ass").write_bytes(b"content")

        result = await mod.get_subtitle_status(media_id=1, track=5, format="ass")
        assert result == {"status": "ready"}

    @pytest.mark.asyncio
    async def test_status_extracting_when_task_running(self, tmp_path):
        import app.api.v1.subtitles as mod

        blocker = asyncio.Event()

        async def forever():
            await blocker.wait()

        key = (1, 5, "ass")
        task = asyncio.create_task(forever())
        mod._subtitle_tasks[key] = task

        result = await mod.get_subtitle_status(media_id=1, track=5, format="ass")
        assert result == {"status": "extracting"}

        blocker.set()
        await asyncio.wait_for(task, timeout=1)

    @pytest.mark.asyncio
    async def test_status_not_started_when_no_task_no_cache(self, tmp_path):
        import app.api.v1.subtitles as mod

        result = await mod.get_subtitle_status(media_id=1, track=5, format="ass")
        assert result == {"status": "not_started"}

    @pytest.mark.asyncio
    async def test_status_not_started_after_task_failed(self, tmp_path):
        """Task that raised and was removed via finally → not_started."""
        import app.api.v1.subtitles as mod

        async def failing():
            raise RuntimeError("boom")

        key = (1, 5, "ass")
        task = asyncio.create_task(failing())
        mod._subtitle_tasks[key] = task

        # Wait for the task to finish (and remove itself from dict via finally)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=1)
        except Exception:
            pass

        # Simulate what _extract_and_cache.finally does
        mod._subtitle_tasks.pop(key, None)

        result = await mod.get_subtitle_status(media_id=1, track=5, format="ass")
        assert result == {"status": "not_started"}

    @pytest.mark.asyncio
    async def test_status_invalid_format_returns_400(self, tmp_path):
        import app.api.v1.subtitles as mod
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle_status(media_id=1, track=0, format="vtt")

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_status_empty_cache_file_is_not_ready(self, tmp_path):
        """A zero-byte cache file must not be reported as ready."""
        import app.api.v1.subtitles as mod

        (mod.SUBTITLE_CACHE_DIR / "1_5.ass").write_bytes(b"")

        result = await mod.get_subtitle_status(media_id=1, track=5, format="ass")
        assert result["status"] != "ready"


# ---------------------------------------------------------------------------
# Unit tests — _extract_and_cache internals
# ---------------------------------------------------------------------------

class TestExtractAndCache:
    """Verify _extract_and_cache writes the file and cleans up _subtitle_tasks."""

    @pytest.fixture(autouse=True)
    def clear_module_state(self, tmp_path):
        import app.api.v1.subtitles as mod
        mod._subtitle_tasks.clear()
        self._orig_dir = mod.SUBTITLE_CACHE_DIR
        mod.SUBTITLE_CACHE_DIR = tmp_path / "subtitles"
        mod.SUBTITLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        yield
        mod.SUBTITLE_CACHE_DIR = self._orig_dir
        mod._subtitle_tasks.clear()

    @pytest.mark.asyncio
    async def test_writes_cache_file_on_success(self, tmp_path):
        import app.api.v1.subtitles as mod

        fake_content = b"[Script Info]\nTitle: test\n"
        mock_reader = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.v1.subtitles.get_virtual_reader", new=AsyncMock(return_value=mock_reader)):
            with patch("app.services.subtitles.mkv_extractor.extract_subtitle_direct",
                       new=AsyncMock(return_value=fake_content)):
                with patch("app.database.async_session_maker", return_value=mock_session):
                    await mod._extract_and_cache(1, 0, 5, "ass")

        cache_file = mod.SUBTITLE_CACHE_DIR / "1_5.ass"
        assert cache_file.exists()
        assert cache_file.read_bytes() == fake_content

    @pytest.mark.asyncio
    async def test_removes_task_from_dict_on_success(self, tmp_path):
        import app.api.v1.subtitles as mod

        key = (1, 5, "ass")
        mock_reader = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # Manually add a placeholder task
        mod._subtitle_tasks[key] = asyncio.create_task(asyncio.sleep(0))

        with patch("app.api.v1.subtitles.get_virtual_reader", new=AsyncMock(return_value=mock_reader)):
            with patch("app.services.subtitles.mkv_extractor.extract_subtitle_direct",
                       new=AsyncMock(return_value=b"content")):
                with patch("app.database.async_session_maker", return_value=mock_session):
                    await mod._extract_and_cache(1, 0, 5, "ass")

        assert key not in mod._subtitle_tasks

    @pytest.mark.asyncio
    async def test_removes_task_from_dict_on_failure(self, tmp_path):
        import app.api.v1.subtitles as mod

        key = (1, 5, "ass")
        mod._subtitle_tasks[key] = asyncio.create_task(asyncio.sleep(0))

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.v1.subtitles.get_virtual_reader", new=AsyncMock(side_effect=RuntimeError("fail"))):
            with patch("app.database.async_session_maker", return_value=mock_session):
                await mod._extract_and_cache(1, 0, 5, "ass")

        assert key not in mod._subtitle_tasks

    @pytest.mark.asyncio
    async def test_no_reader_does_not_write_cache(self, tmp_path):
        import app.api.v1.subtitles as mod

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.api.v1.subtitles.get_virtual_reader", new=AsyncMock(return_value=None)):
            with patch("app.database.async_session_maker", return_value=mock_session):
                await mod._extract_and_cache(1, 0, 5, "ass")

        assert not (mod.SUBTITLE_CACHE_DIR / "1_5.ass").exists()
