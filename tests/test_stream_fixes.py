"""Confirmation tests for the three streaming bug-fixes.

Fix 1 — Resource Leak: stream_generator detects disconnect and calls
         release_reader() so Pyrogram clients are returned to the pool.

Fix 2 — WebView 206: stream_raw always returns HTTP 206 with correct
         Content-Range and Content-Length headers.
"""

import asyncio
import contextlib
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response

import app.services.streaming.manager as manager_module
from app.api.deps import get_stream_user
from app.api.v1.stream import parse_range_header
from app.core.security import INTERNAL_STREAM_TOKEN, create_access_token
from app.main import app
from app.services.streaming.manager import get_virtual_reader, release_reader
from app.services.streaming.reader import VirtualStreamReader

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

STREAM_BASE = "/api/v1/stream"
MEDIA_ID = 1
TOTAL = 4 * 1024 * 1024  # 4 MB virtual file

_POOL_STATUS_OK = {
    "total_clients": 4,
    "clients_in_use": 0,
    "clients_available": 4,
    "pool_pressure": 0.0,
}


def make_mock_reader(total: int = TOTAL) -> MagicMock:
    """Create a VirtualStreamReader mock that serves predictable bytes."""
    reader = MagicMock(spec=VirtualStreamReader)
    reader.total_size = total
    reader._clients = []
    reader._parts = []

    async def fake_read_range(start: int, end: int | None = None):
        _end = total if end is None else end
        size = max(0, min(_end, total) - max(0, start))
        if size > 0:
            yield b"x" * size

    reader.read_range = fake_read_range
    return reader


# ---------------------------------------------------------------------------
# Autouse fixtures — isolate module-level state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_reader_cache():
    manager_module._reader_cache.clear()
    yield
    manager_module._reader_cache.clear()


@pytest.fixture(autouse=True)
def skip_stream_auth():
    app.dependency_overrides[get_stream_user] = lambda: None
    yield
    app.dependency_overrides.pop(get_stream_user, None)


# ---------------------------------------------------------------------------
# Stream/subtitle auth
# ---------------------------------------------------------------------------


class TestStreamAuth:
    async def test_anonymous_request_rejected(self):
        app.dependency_overrides.pop(get_stream_user, None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.get("/api/v1/stream/raw/1")).status_code == 401
            assert (await c.get("/api/v1/subtitles/1/status")).status_code == 401

    async def test_cookie_token_accepted(self):
        user = MagicMock()
        session = AsyncMock()
        session.get.return_value = user
        request = MagicMock(query_params={}, cookies={"token": create_access_token({"sub": "1"})})
        assert await get_stream_user(request, session, token=None) is user

    async def test_internal_token_skips_user_lookup(self):
        request = MagicMock(query_params={"internal": INTERNAL_STREAM_TOKEN}, cookies={})
        session = AsyncMock()
        assert await get_stream_user(request, session=session, token=None) is None
        session.get.assert_not_awaited()


# ---------------------------------------------------------------------------
# Fix 2 — parse_range_header (pure function)
# ---------------------------------------------------------------------------


class TestParseRangeHeader:
    """Exhaustive tests for the pure parse_range_header helper."""

    N = 10 * 1024 * 1024  # 10 MB

    def test_no_header_returns_full_file(self):
        s, e = parse_range_header(None, self.N)
        assert s == 0
        assert e == self.N - 1

    def test_open_range_from_zero(self):
        s, e = parse_range_header("bytes=0-", self.N)
        assert s == 0
        assert e == self.N - 1

    def test_open_range_mid_file(self):
        s, e = parse_range_header("bytes=1_000_000-".replace("_", ""), self.N)
        assert s == 1_000_000
        assert e == self.N - 1

    def test_closed_range_start_and_end(self):
        s, e = parse_range_header("bytes=0-1023", self.N)
        assert s == 0
        assert e == 1023

    def test_content_length_from_closed_range(self):
        s, e = parse_range_header("bytes=0-1023", self.N)
        assert e - s + 1 == 1024

    def test_content_length_of_full_file(self):
        s, e = parse_range_header(None, self.N)
        assert e - s + 1 == self.N

    def test_invalid_header_falls_back_to_full_file(self):
        s, e = parse_range_header("bad-header", self.N)
        assert s == 0
        assert e == self.N - 1

    def test_end_clamped_to_total_minus_one(self):
        s, e = parse_range_header(f"bytes=0-{self.N + 9999}", self.N)
        assert e == self.N - 1

    def test_start_clamped_when_past_end(self):
        # start beyond total → clamped to total-1; end = max(start, ...) = start
        s, e = parse_range_header(f"bytes={self.N + 1}-", self.N)
        assert s == self.N - 1
        assert e == self.N - 1

    def test_mid_range_content_length(self):
        s, e = parse_range_header("bytes=512000-1023999", self.N)
        assert e - s + 1 == 512_000


# ---------------------------------------------------------------------------
# Fix 2 — HTTP 206 headers via the real ASGI app
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_reader_get(mocker) -> MagicMock:
    """Patch get_virtual_reader in the stream module to return a mock reader."""
    reader = make_mock_reader()
    mocker.patch(
        "app.api.v1.stream.get_virtual_reader",
        new_callable=AsyncMock,
        return_value=reader,
    )
    mocker.patch(
        "app.api.v1.stream.worker_manager.pool_status",
        return_value=_POOL_STATUS_OK,
    )
    mocker.patch(
        "app.api.v1.stream.release_reader",
        new_callable=AsyncMock,
    )
    # Disconnect never happens during header-only tests
    mocker.patch(
        "starlette.requests.Request.is_disconnected",
        new_callable=AsyncMock,
        return_value=False,
    )
    return reader


class TestStreamRaw206:
    """stream_raw must always return 206 with correct Range headers."""

    async def _get(self, headers: dict | None = None) -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(
                f"{STREAM_BASE}/raw/{MEDIA_ID}",
                headers=headers or {},
            )

    async def test_no_range_header_returns_206(self, mock_reader_get):
        resp = await self._get()
        assert resp.status_code == 206

    async def test_range_header_returns_206(self, mock_reader_get):
        resp = await self._get({"Range": "bytes=0-1023"})
        assert resp.status_code == 206

    async def test_open_range_bytes0dash_returns_206(self, mock_reader_get):
        resp = await self._get({"Range": "bytes=0-"})
        assert resp.status_code == 206

    async def test_open_range_mid_file_returns_206(self, mock_reader_get):
        resp = await self._get({"Range": "bytes=1048576-"})
        assert resp.status_code == 206

    # --- Content-Range ---

    async def test_no_range_content_range_is_full_file(self, mock_reader_get):
        resp = await self._get()
        expected = f"bytes 0-{TOTAL - 1}/{TOTAL}"
        assert resp.headers["content-range"] == expected

    async def test_closed_range_content_range_header(self, mock_reader_get):
        resp = await self._get({"Range": "bytes=0-1023"})
        assert resp.headers["content-range"] == f"bytes 0-1023/{TOTAL}"

    async def test_open_range_mid_file_content_range(self, mock_reader_get):
        resp = await self._get({"Range": "bytes=1048576-"})
        expected = f"bytes 1048576-{TOTAL - 1}/{TOTAL}"
        assert resp.headers["content-range"] == expected

    # --- Content-Length ---

    async def test_content_length_matches_full_file(self, mock_reader_get):
        resp = await self._get()
        assert resp.headers["content-length"] == str(TOTAL)

    async def test_content_length_matches_partial_range(self, mock_reader_get):
        resp = await self._get({"Range": "bytes=0-1023"})
        assert resp.headers["content-length"] == "1024"

    async def test_content_length_matches_open_range(self, mock_reader_get):
        start = 1_048_576
        resp = await self._get({"Range": f"bytes={start}-"})
        expected = str(TOTAL - start)
        assert resp.headers["content-length"] == expected

    # --- Accept-Ranges must always be present ---

    async def test_accept_ranges_always_present(self, mock_reader_get):
        resp = await self._get()
        assert resp.headers.get("accept-ranges") == "bytes"

    async def test_accept_ranges_present_with_range_header(self, mock_reader_get):
        resp = await self._get({"Range": "bytes=0-1023"})
        assert resp.headers.get("accept-ranges") == "bytes"


class TestStreamPlayHeaders:
    """/play is a live remux: a plain 200. Chromium (desktop and the Android TV WebView)
    rejected the invalid "Content-Range: bytes 0-*/*" it used to send as a format error."""

    async def test_play_is_200_without_ranges(self, mock_reader_get, mocker):
        mocker.patch(
            "app.api.v1.stream._get_keyframe_for_time", new_callable=AsyncMock, return_value=0.0
        )

        async def remux(*_):
            yield b"fmp4"

        mocker.patch("app.api.v1.stream.ffmpeg_remuxer.stream", side_effect=remux)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"{STREAM_BASE}/play/{MEDIA_ID}")
        assert resp.status_code == 200
        assert "content-range" not in resp.headers
        assert "accept-ranges" not in resp.headers
        assert resp.content == b"fmp4"


async def test_abandoned_remux_frees_its_reader_thread(mocker):
    import sys
    import threading

    from app.services.ffmpeg import RemuxOptions, ffmpeg_remuxer

    producer = "import sys\nwhile True: sys.stdout.buffer.write(b'x' * 65536)"
    mocker.patch.object(ffmpeg_remuxer, "build_command", return_value=[sys.executable, "-c", producer])
    stream = ffmpeg_remuxer.stream("in", RemuxOptions())
    await stream.__anext__()
    await asyncio.sleep(0.5)  # the player stops reading (60 s buffered): the queue fills up
    await stream.aclose()  # then seeks out of the buffer or leaves

    def reader_alive():
        return any(t.name.endswith("(reader_thread)") and t.is_alive() for t in threading.enumerate())

    for _ in range(50):
        if not reader_alive():
            break
        await asyncio.sleep(0.1)
    assert not reader_alive()


def test_hevc_is_remuxed_as_hvc1_for_safari():
    from app.services.ffmpeg import RemuxOptions, ffmpeg_remuxer

    hevc = ffmpeg_remuxer.build_command("in", RemuxOptions(hevc=True))
    assert hevc[hevc.index("-tag:v") + 1] == "hvc1"
    assert "-tag:v" not in ffmpeg_remuxer.build_command("in", RemuxOptions())


# ---------------------------------------------------------------------------
# Fix 1 — Resource Leak: disconnect triggers release_reader
# ---------------------------------------------------------------------------


@pytest.fixture
def stream_mocks(mocker) -> tuple[MagicMock, AsyncMock]:
    """Common mocks for stream_generator disconnect/cancel tests."""
    reader = make_mock_reader()
    mocker.patch(
        "app.api.v1.stream.get_virtual_reader",
        new_callable=AsyncMock,
        return_value=reader,
    )
    mock_release = mocker.patch(
        "app.api.v1.stream.release_reader",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "app.api.v1.stream.worker_manager.pool_status",
        return_value=_POOL_STATUS_OK,
    )
    return reader, mock_release


class TestStreamGeneratorDisconnect:
    """Verify that abrupt disconnects always release the persistent reader."""

    async def _call(self, headers: dict | None = None) -> object:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(
                f"{STREAM_BASE}/raw/{MEDIA_ID}",
                headers=headers or {},
            )

    # --- Normal completion: reader must NOT be released ---

    async def test_normal_completion_does_not_release_reader(self, mocker, stream_mocks):
        _, mock_release = stream_mocks
        mocker.patch(
            "starlette.requests.Request.is_disconnected",
            new_callable=AsyncMock,
            return_value=False,  # never disconnects
        )
        await self._call()
        mock_release.assert_not_called()

    # --- is_disconnected() → True: reader must be released ---

    async def test_disconnect_detected_calls_release_reader(self, mocker, stream_mocks):
        reader, mock_release = stream_mocks

        # Reader yields one large chunk; disconnect is signalled after it
        async def one_chunk_then_disconnect(start, end=None):
            yield b"x" * 1024

        reader.read_range = one_chunk_then_disconnect
        mocker.patch(
            "starlette.requests.Request.is_disconnected",
            new_callable=AsyncMock,
            return_value=True,  # always disconnected
        )
        await self._call()
        mock_release.assert_called_once_with(MEDIA_ID, only_if_idle=True)

    async def test_disconnect_release_called_with_correct_media_id(self, mocker, stream_mocks):
        reader, mock_release = stream_mocks
        target_id = MEDIA_ID

        async def one_chunk(start, end=None):
            yield b"y" * 512

        reader.read_range = one_chunk
        mocker.patch(
            "starlette.requests.Request.is_disconnected",
            new_callable=AsyncMock,
            return_value=True,
        )
        await self._call()
        args, _ = mock_release.call_args
        assert args[0] == target_id

    # --- CancelledError: reader must be released, error re-raised ---

    async def test_cancellederror_releases_reader(self, mocker, stream_mocks):
        reader, mock_release = stream_mocks
        mocker.patch(
            "starlette.requests.Request.is_disconnected",
            new_callable=AsyncMock,
            return_value=False,
        )

        async def cancelling_read_range(start, end=None):
            yield b"x" * 512
            raise asyncio.CancelledError()

        reader.read_range = cancelling_read_range

        # CancelledError may surface as a connection error in httpx —
        # either way the important post-condition is that release was called.
        with contextlib.suppress(BaseException):
            await self._call()

        mock_release.assert_called_once_with(MEDIA_ID, only_if_idle=True)

    async def test_normal_complete_then_disconnect_on_second_request(self, mocker, stream_mocks):
        """First request completes normally (no release); second request
        detects disconnect (release must be called once, not twice)."""
        reader, mock_release = stream_mocks

        disconnect_flag = {"val": False}
        call_count = {"n": 0}

        async def is_dc_side_effect():
            call_count["n"] += 1
            return disconnect_flag["val"]

        mocker.patch(
            "starlette.requests.Request.is_disconnected",
            side_effect=is_dc_side_effect,
        )

        # First request — no disconnect
        await self._call({"Range": "bytes=0-1023"})
        mock_release.assert_not_called()

        # Second request — disconnect
        disconnect_flag["val"] = True
        async def one_chunk(start, end=None):
            yield b"z" * 512

        reader.read_range = one_chunk
        await self._call({"Range": "bytes=0-511"})
        mock_release.assert_called_once_with(MEDIA_ID, only_if_idle=True)


# ---------------------------------------------------------------------------
# Reader cache and release (manager)
# ---------------------------------------------------------------------------


class TestReaderManager:
    """Persistent readers: cached per media, released with their clients."""

    @pytest_asyncio.fixture
    async def media_with_parts(self, test_session):
        from app.models.media import MediaItem, MediaPart, MediaType

        media = MediaItem(title="Fix-Test Film", media_type=MediaType.MOVIE, duration_seconds=100)
        test_session.add(media)
        await test_session.flush()
        part = MediaPart(
            media_item_id=media.id,
            telegram_file_id="fid_fix",
            part_index=0,
            start_byte=0,
            end_byte=1_048_576,
            file_size=1_048_576,
            channel_id=100,
            topic_id=None,
            message_id=999,
        )
        test_session.add(part)
        await test_session.commit()
        return media, part

    async def test_missing_media_has_no_reader(self, test_session):
        assert await get_virtual_reader(test_session, 88888) is None

    async def test_persistent_reader_is_reused(self, test_session, media_with_parts):
        media, _ = media_with_parts
        first = await get_virtual_reader(test_session, media.id, persistent=True)
        assert await get_virtual_reader(test_session, media.id, persistent=True) is first

    async def test_release_gives_the_clients_back(self, mocker, test_session, media_with_parts):
        media, _ = media_with_parts
        release = mocker.patch("app.services.streaming.manager.worker_manager.release_clients")
        reader = await get_virtual_reader(test_session, media.id, persistent=True)
        assert reader is not None
        client = MagicMock()
        reader._clients = [client]

        await release_reader(media.id)

        release.assert_called_once_with([client])
        assert reader._force_released and reader._clients == []
        assert media.id not in manager_module._reader_cache

    async def test_idle_only_release_keeps_reader_in_use(self, mocker, test_session, media_with_parts):
        media, _ = media_with_parts
        release = mocker.patch("app.services.streaming.manager.worker_manager.release_clients")
        reader = await get_virtual_reader(test_session, media.id, persistent=True)
        assert reader is not None
        reader._clients = [MagicMock()]
        reader._active_streams = 1  # e.g. ffmpeg's next range request

        await release_reader(media.id, only_if_idle=True)
        assert not reader._force_released
        release.assert_not_called()

        reader._active_streams = 0
        await release_reader(media.id, only_if_idle=True)
        assert reader._force_released
        release.assert_called_once()

    async def test_reader_cached_during_query_is_reused(self, test_session, media_with_parts):
        media, _ = media_with_parts
        winner = MagicMock()
        real_execute = test_session.execute

        async def execute_while_other_request_caches(*args, **kwargs):
            manager_module._reader_cache[media.id] = (winner, time.time())
            return await real_execute(*args, **kwargs)

        test_session.execute = execute_while_other_request_caches
        assert await get_virtual_reader(test_session, media.id, persistent=True) is winner
