"""Tests for the non-blocking subtitle endpoint and the per-media extraction task.

Tests:
- Cache miss → 202 {"status": "extracting", "retry_after": 2}, one task per media
- Cached file → 200; extraction just finished without the track → 404
- /status: ready / extracting / failed / not_started
- _extract: caches through cache_all_subtitle_tracks, always unregisters itself
- pre_extract_subtitles: skips cached media, waits for the shared task otherwise
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.subtitles import cache

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


@pytest.fixture(autouse=True)
def subtitle_state(tmp_path, monkeypatch):
    """Empty task registry and a tmp cache dir for every test."""
    monkeypatch.setattr(cache, "SUBTITLE_CACHE_DIR", tmp_path / "subtitles")
    cache.SUBTITLE_CACHE_DIR.mkdir()
    cache._tasks.clear()
    cache._finished_at.clear()
    yield
    for task in cache._tasks.values():
        task.cancel()
    cache._tasks.clear()
    cache._finished_at.clear()


def _blocked_extract(blocker: asyncio.Event, calls: list):
    async def extract(media_id, full_read=True):
        calls.append(media_id)
        await blocker.wait()
        return 0
    return extract


# ---------------------------------------------------------------------------
# get_subtitle
# ---------------------------------------------------------------------------

class TestGetSubtitle:
    async def test_cache_miss_returns_202_and_starts_extraction(self):
        import app.api.v1.subtitles as mod

        with patch.object(mod, "extraction_task") as start:
            resp = await mod.get_subtitle(
                media_id=1, session=_make_session(_make_media([_make_stream(5)])), track=5, format="ass"
            )

        assert resp.status_code == 202
        assert json.loads(bytes(resp.body)) == {"status": "extracting", "retry_after": 2}
        assert resp.headers["retry-after"] == "2"
        start.assert_called_once_with(1)

    async def test_cache_hit_returns_200(self):
        import app.api.v1.subtitles as mod

        cache.subtitle_file(1, 5, "ass").write_bytes(b"[Script Info]\nTitle: test\n")

        resp = await mod.get_subtitle(
            media_id=1, session=_make_session(_make_media([_make_stream(5)])), track=5, format="ass"
        )

        assert resp.status_code == 200
        assert b"[Script Info]" in resp.body

    async def test_requests_for_two_tracks_share_one_task(self, monkeypatch):
        import app.api.v1.subtitles as mod

        blocker, calls = asyncio.Event(), []
        monkeypatch.setattr(cache, "_extract", _blocked_extract(blocker, calls))
        media = _make_media([_make_stream(5), _make_stream(6)])

        for track in (5, 6, 5):
            resp = await mod.get_subtitle(media_id=1, session=_make_session(media), track=track, format="ass")
            assert resp.status_code == 202
        await asyncio.sleep(0)

        assert calls == [1]
        blocker.set()

    async def test_finished_without_the_track_returns_404(self):
        from fastapi import HTTPException

        import app.api.v1.subtitles as mod

        cache._finished_at[1] = time.monotonic()

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle(
                media_id=1, session=_make_session(_make_media([_make_stream(5)])), track=5, format="ass"
            )
        assert exc_info.value.status_code == 404

    async def test_retried_after_the_cooldown(self):
        import app.api.v1.subtitles as mod

        cache._finished_at[1] = time.monotonic() - cache.RETRY_AFTER - 1
        with patch.object(mod, "extraction_task") as start:
            resp = await mod.get_subtitle(
                media_id=1, session=_make_session(_make_media([_make_stream(5)])), track=5, format="ass"
            )
        assert resp.status_code == 202
        start.assert_called_once_with(1)

    async def test_invalid_track_returns_400(self):
        from fastapi import HTTPException

        import app.api.v1.subtitles as mod

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle(
                media_id=1, session=_make_session(_make_media([_make_stream(3)])), track=99, format="ass"
            )
        assert exc_info.value.status_code == 400

    async def test_invalid_format_returns_400(self):
        from fastapi import HTTPException

        import app.api.v1.subtitles as mod

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle(
                media_id=1, session=_make_session(_make_media([_make_stream(0)])), track=0, format="vtt"
            )
        assert exc_info.value.status_code == 400

    async def test_media_not_found_returns_404(self):
        from fastapi import HTTPException

        import app.api.v1.subtitles as mod

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle(media_id=999, session=_make_session(None), track=0, format="ass")
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

class TestGetSubtitleStatus:
    async def test_ready_when_cached(self):
        import app.api.v1.subtitles as mod

        cache.subtitle_file(1, 5, "ass").write_bytes(b"content")
        assert await mod.get_subtitle_status(media_id=1, track=5, format="ass") == {"status": "ready"}

    async def test_extracting_while_task_runs(self):
        import app.api.v1.subtitles as mod

        cache._tasks[1] = MagicMock()
        assert await mod.get_subtitle_status(media_id=1, track=5, format="ass") == {"status": "extracting"}

    async def test_failed_after_extraction_without_the_track(self):
        import app.api.v1.subtitles as mod

        cache._finished_at[1] = time.monotonic()
        assert await mod.get_subtitle_status(media_id=1, track=5, format="ass") == {"status": "failed"}

    async def test_not_started(self):
        import app.api.v1.subtitles as mod

        assert await mod.get_subtitle_status(media_id=1, track=5, format="ass") == {"status": "not_started"}

    async def test_invalid_format_returns_400(self):
        from fastapi import HTTPException

        import app.api.v1.subtitles as mod

        with pytest.raises(HTTPException) as exc_info:
            await mod.get_subtitle_status(media_id=1, track=0, format="vtt")
        assert exc_info.value.status_code == 400

    async def test_empty_cache_file_is_not_ready(self):
        import app.api.v1.subtitles as mod

        cache.subtitle_file(1, 5, "ass").write_bytes(b"")
        result = await mod.get_subtitle_status(media_id=1, track=5, format="ass")
        assert result["status"] != "ready"


# ---------------------------------------------------------------------------
# cache._extract / pre_extract_subtitles
# ---------------------------------------------------------------------------

def _session_maker(media):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = _make_session(media)
    return maker


class TestExtract:
    async def test_caches_all_tracks_in_stream_order(self):
        reader = MagicMock()
        cache_all = AsyncMock(return_value=2)
        with (
            patch("app.database.async_session_maker", _session_maker(_make_media([_make_stream(6), _make_stream(2)]))),
            patch.object(cache, "get_virtual_reader", AsyncMock(return_value=reader)),
            patch.object(cache, "cache_all_subtitle_tracks", cache_all),
        ):
            assert await cache.extraction_task(1) == 2

        cache_all.assert_awaited_once_with(reader, 1, [2, 6], True)
        assert 1 not in cache._tasks
        assert cache.finished_recently(1)

    async def test_failure_is_logged_and_unregisters(self):
        with (
            patch("app.database.async_session_maker", _session_maker(_make_media([_make_stream(2)]))),
            patch.object(cache, "get_virtual_reader", AsyncMock(side_effect=RuntimeError("fail"))),
        ):
            assert await cache.extraction_task(1) == 0

        assert 1 not in cache._tasks
        assert cache.finished_recently(1)

    async def test_no_reader_writes_nothing(self):
        with (
            patch("app.database.async_session_maker", _session_maker(_make_media([_make_stream(2)]))),
            patch.object(cache, "get_virtual_reader", AsyncMock(return_value=None)),
        ):
            assert await cache.extraction_task(1) == 0

        assert not any(cache.SUBTITLE_CACHE_DIR.iterdir())


class TestPreExtractSubtitles:
    async def test_skips_media_with_a_cached_track(self, monkeypatch):
        cache.subtitle_file(1, 6, "ass").write_bytes(b"x")
        start = MagicMock()
        monkeypatch.setattr(cache, "extraction_task", start)

        media = _make_media([_make_stream(2), _make_stream(6)])
        assert await cache.pre_extract_subtitles(1, _make_session(media)) == 0
        start.assert_not_called()

    async def test_waits_for_the_shared_task(self, monkeypatch):
        extract = AsyncMock(return_value=3)
        monkeypatch.setattr(cache, "_extract", extract)

        media = _make_media([_make_stream(2)])
        assert await cache.pre_extract_subtitles(1, _make_session(media)) == 3
        extract.assert_awaited_once_with(1, False)  # background: no whole-file reads

    async def test_background_run_does_not_hold_off_a_request(self):
        # A warm-up that skipped a track must not make the player's request wait 60 s
        with (
            patch("app.database.async_session_maker", _session_maker(_make_media([_make_stream(2)]))),
            patch.object(cache, "get_virtual_reader", AsyncMock(return_value=MagicMock())),
            patch.object(cache, "cache_all_subtitle_tracks", AsyncMock(return_value=0)),
        ):
            await cache.extraction_task(1, full_read=False)
            assert not cache.finished_recently(1)
            await cache.extraction_task(1)
            assert cache.finished_recently(1)


# ---------------------------------------------------------------------------
# get_font_file — must not read outside the media's font cache
# ---------------------------------------------------------------------------

class TestGetFontFile:
    @pytest.fixture(autouse=True)
    def font_cache(self, tmp_path, monkeypatch):
        import app.api.v1.subtitles as mod

        monkeypatch.setattr(mod, "FONT_CACHE_DIR", tmp_path / "fonts")
        (tmp_path / "fonts" / "1").mkdir(parents=True)
        (tmp_path / "fonts" / "1" / "Arial.ttf").write_bytes(b"font")
        (tmp_path / "fonts" / "secret.txt").write_bytes(b"secret")

    async def test_cached_font_served(self):
        import app.api.v1.subtitles as mod

        resp = await mod.get_font_file(media_id=1, filename="Arial.ttf", session=MagicMock())
        assert resp.body == b"font"

    @pytest.mark.parametrize("filename", ["..", "../secret.txt", "..\\secret.txt"])
    async def test_traversal_rejected(self, filename):
        from fastapi import HTTPException

        import app.api.v1.subtitles as mod

        with pytest.raises(HTTPException) as exc:
            await mod.get_font_file(media_id=1, filename=filename, session=MagicMock())
        assert exc.value.status_code == 404


class TestGetFonts:
    @pytest.fixture
    def fonts(self, tmp_path, monkeypatch):
        """Font cache in tmp; returns the extractor mock (what Telegram would give)."""
        import app.api.v1.subtitles as mod

        monkeypatch.setattr(mod, "FONT_CACHE_DIR", tmp_path / "fonts")
        monkeypatch.setattr(cache, "FONT_CACHE_DIR", tmp_path / "fonts")
        monkeypatch.setattr(cache, "get_virtual_reader", AsyncMock(return_value=MagicMock()))
        extract = AsyncMock(return_value=[])
        monkeypatch.setattr(cache.subtitle_extractor, "extract_all_fonts_from_reader", extract)
        return extract

    async def test_media_without_fonts_is_read_once(self, fonts):
        import app.api.v1.subtitles as mod

        for _ in range(3):  # every subtitle toggle asks again
            resp = await mod.get_fonts(media_id=1, session=MagicMock())
            assert resp["fonts"] == []

        fonts.assert_awaited_once()

    async def test_extracted_fonts_are_listed(self, fonts, tmp_path):
        import app.api.v1.subtitles as mod
        from app.services.subtitles.models import AttachedFont

        fonts.return_value = [AttachedFont(filename="A.ttf", mimetype="font/ttf", data=b"f", font_names=[])]

        first = await mod.get_fonts(media_id=1, session=MagicMock())
        again = await mod.get_fonts(media_id=1, session=MagicMock())

        assert [f["filename"] for f in first["fonts"]] == ["A.ttf"] == [f["filename"] for f in again["fonts"]]
        assert first["fonts"][0]["url"] == "/api/v1/subtitles/1/font/A.ttf"
        assert (tmp_path / "fonts" / "1" / "A.ttf").read_bytes() == b"f"
        fonts.assert_awaited_once()
