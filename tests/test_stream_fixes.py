"""Confirmation tests for the three streaming bug-fixes.

Fix 1 — Resource Leak: stream_generator detects disconnect and calls
         release_reader() so Pyrogram clients are returned to the pool.

Fix 2 — WebView 206: stream_raw always returns HTTP 206 with correct
         Content-Range and Content-Length headers.

Fix 3 — Ring Buffer: crash_log records events; flushes to disk only on
         critical failure (never during normal operation).
"""

import asyncio
import contextlib
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.services.streaming.crash_log as crash_log_module
import app.services.streaming.manager as manager_module
from app.api.v1.stream import parse_range_header
from app.main import app
from app.services.streaming.crash_log import flush as crash_flush
from app.services.streaming.crash_log import record as crash_record
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
def clear_crash_ring():
    crash_log_module._ring.clear()
    yield
    crash_log_module._ring.clear()


@pytest.fixture(autouse=True)
def clear_reader_cache():
    manager_module._reader_cache.clear()
    yield
    manager_module._reader_cache.clear()


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

    async def _get(self, headers: dict | None = None) -> object:
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
        mock_release.assert_called_once_with(MEDIA_ID)

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

        mock_release.assert_called_once_with(MEDIA_ID)

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
        mock_release.assert_called_once_with(MEDIA_ID)


# ---------------------------------------------------------------------------
# Fix 3 — Ring Buffer (crash_log module)
# ---------------------------------------------------------------------------


class TestCrashLogRingBuffer:
    """crash_log.record() and the ring buffer capacity."""

    def test_record_appends_entry(self):
        crash_record("test.event", key="value")
        assert len(crash_log_module._ring) == 1
        entry = crash_log_module._ring[-1]
        assert entry["event"] == "test.event"
        assert entry["key"] == "value"

    def test_record_includes_timestamp(self):
        before = time.time()
        crash_record("ts.check")
        after = time.time()
        assert before <= crash_log_module._ring[-1]["ts"] <= after

    def test_ring_maxlen_is_500(self):
        assert crash_log_module._ring.maxlen == 500

    def test_multiple_records_accumulate(self):
        for i in range(10):
            crash_record("ev", i=i)
        assert len(crash_log_module._ring) == 10

    def test_oldest_entry_evicted_when_full(self):
        for i in range(501):
            crash_record("ev", seq=i)
        assert len(crash_log_module._ring) == 500
        # seq=0 was evicted; first surviving entry has seq=1
        assert crash_log_module._ring[0]["seq"] == 1
        assert crash_log_module._ring[-1]["seq"] == 500

    def test_fields_stored_correctly(self):
        crash_record("complex", part_id=42, client_id=99, error="boom")
        entry = crash_log_module._ring[-1]
        assert entry["part_id"] == 42
        assert entry["client_id"] == 99
        assert entry["error"] == "boom"


class TestCrashLogFlush:
    """crash_log.flush() writes JSON only on demand; silent on I/O errors."""

    def test_flush_creates_file(self, mocker, tmp_path):
        crash_path = tmp_path / "crash_stream.json"
        mocker.patch.object(crash_log_module, "_CRASH_LOG_PATH", crash_path)
        crash_record("pre.flush")
        crash_flush("test crash")
        assert crash_path.exists()

    def test_flush_json_structure(self, mocker, tmp_path):
        crash_path = tmp_path / "crash_stream.json"
        mocker.patch.object(crash_log_module, "_CRASH_LOG_PATH", crash_path)
        crash_record("alpha", x=1)
        crash_record("beta", x=2)
        crash_flush("reason text")
        data = json.loads(crash_path.read_text())
        assert data["reason"] == "reason text"
        assert data["total_entries"] == 2
        assert len(data["entries"]) == 2
        assert data["entries"][0]["event"] == "alpha"
        assert data["entries"][1]["event"] == "beta"

    def test_flush_includes_flushed_at_timestamp(self, mocker, tmp_path):
        crash_path = tmp_path / "crash_stream.json"
        mocker.patch.object(crash_log_module, "_CRASH_LOG_PATH", crash_path)
        before = time.time()
        crash_flush("ts test")
        data = json.loads(crash_path.read_text())
        assert data["flushed_at"] >= before

    def test_flush_silent_on_oserror(self, mocker):
        bad_path = Path("/nonexistent_dir_xyz/crash.json")
        mocker.patch.object(crash_log_module, "_CRASH_LOG_PATH", bad_path)
        crash_record("event")
        crash_flush("should not raise")  # must not raise OSError

    def test_record_never_writes_to_disk(self, mocker, tmp_path):
        crash_path = tmp_path / "crash_stream.json"
        mocker.patch.object(crash_log_module, "_CRASH_LOG_PATH", crash_path)
        for _ in range(200):
            crash_record("normal.op", data="payload")
        assert not crash_path.exists(), "crash_stream.json written during normal operation"

    def test_flush_empty_ring_writes_empty_entries(self, mocker, tmp_path):
        crash_path = tmp_path / "crash_stream.json"
        mocker.patch.object(crash_log_module, "_CRASH_LOG_PATH", crash_path)
        # ring is empty (autouse fixture cleared it)
        crash_flush("empty ring")
        data = json.loads(crash_path.read_text())
        assert data["entries"] == []
        assert data["total_entries"] == 0

    def test_flush_preserves_entry_order(self, mocker, tmp_path):
        crash_path = tmp_path / "crash_stream.json"
        mocker.patch.object(crash_log_module, "_CRASH_LOG_PATH", crash_path)
        for i in range(5):
            crash_record("seq", n=i)
        crash_flush("order check")
        data = json.loads(crash_path.read_text())
        ns = [e["n"] for e in data["entries"]]
        assert ns == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Fix 3 — crash_log integration: manager writes events to the ring
# ---------------------------------------------------------------------------


class TestCrashLogManagerIntegration:
    """Manager operations write the expected events to the ring buffer."""

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

    async def test_missing_media_records_not_found(self, test_session):
        result = await get_virtual_reader(test_session, 88888)
        assert result is None
        events = [e["event"] for e in crash_log_module._ring]
        assert "reader.not_found" in events

    async def test_reader_created_records_event(self, test_session, media_with_parts):
        media, _ = media_with_parts
        await get_virtual_reader(test_session, media.id, persistent=False)
        events = [e["event"] for e in crash_log_module._ring]
        assert "reader.created" in events

    async def test_cache_hit_records_event(self, test_session, media_with_parts):
        media, _ = media_with_parts
        await get_virtual_reader(test_session, media.id, persistent=True)
        crash_log_module._ring.clear()  # clear creation event
        # Second call → cache hit
        await get_virtual_reader(test_session, media.id, persistent=True)
        events = [e["event"] for e in crash_log_module._ring]
        assert "reader.cache_hit" in events

    async def test_force_release_with_clients_records_event(self, mocker, test_session, media_with_parts):
        media, _ = media_with_parts
        mocker.patch("app.services.streaming.manager.worker_manager.release_clients")
        reader = await get_virtual_reader(test_session, media.id, persistent=True)
        # Inject a fake client so the release branch is taken
        reader._clients = [MagicMock()]
        crash_log_module._ring.clear()

        await release_reader(media.id)

        events = [e["event"] for e in crash_log_module._ring]
        assert "reader.force_released" in events

    async def test_force_release_event_contains_media_id(self, mocker, test_session, media_with_parts):
        media, _ = media_with_parts
        mocker.patch("app.services.streaming.manager.worker_manager.release_clients")
        reader = await get_virtual_reader(test_session, media.id, persistent=True)
        reader._clients = [MagicMock()]
        crash_log_module._ring.clear()

        await release_reader(media.id)

        release_entries = [e for e in crash_log_module._ring if e["event"] == "reader.force_released"]
        assert release_entries[0]["media_id"] == media.id
