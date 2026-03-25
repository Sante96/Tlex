"""Tests for the streaming pipeline (cache, reader, manager)."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.streaming.cache as cache_module
import app.services.streaming.manager as manager_module
from app.models.media import MediaItem, MediaPart, MediaType
from app.services.streaming.cache import (
    PYROGRAM_CHUNK_SIZE,
    _cache_chunk,
    _get_cached_chunk,
    invalidate_file_id_cache,
)
from app.services.streaming.manager import (
    cleanup_stale_readers,
    get_virtual_reader,
    release_reader,
)
from app.services.streaming.reader import VirtualStreamReader

# ---------------------------------------------------------------------------
# Cache isolation — mandatory to prevent state leaking between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_all_caches():
    cache_module._CHUNK_CACHE.clear()
    cache_module._FILE_ID_CACHE.clear()
    manager_module._reader_cache.clear()
    yield
    cache_module._CHUNK_CACHE.clear()
    cache_module._FILE_ID_CACHE.clear()
    manager_module._reader_cache.clear()


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_part(part_id, start, end, part_index=None):
    """Create a real MediaPart instance (no DB session needed)."""
    return MediaPart(
        id=part_id,
        media_item_id=1,
        telegram_file_id=f"file_id_{part_id}",
        part_index=part_index if part_index is not None else part_id,
        start_byte=start,
        end_byte=end,
        file_size=end - start,
        channel_id=100,
        topic_id=None,
        message_id=part_id * 10,
    )


def make_media(parts, media_id=1):
    """Create a mock MediaItem with the given parts list."""
    item = MagicMock(spec=MediaItem)
    item.id = media_id
    item.parts = parts
    item.duration_seconds = 3600
    return item


def make_reader(parts, media_id=1):
    """Create a VirtualStreamReader backed by mocks (no real DB/Telegram)."""
    session = MagicMock(spec=AsyncSession)
    media = make_media(parts, media_id)
    return VirtualStreamReader(media_item=media, session=session)


# ---------------------------------------------------------------------------
# TestMediaPartMath — pure Python, no async, no mocks
# ---------------------------------------------------------------------------


class TestMediaPartMath:
    """MediaPart.contains_byte() and .local_offset() boundary checks."""

    def setup_method(self):
        self.part = make_part(1, 0, 1000)

    def test_contains_byte_middle(self):
        assert self.part.contains_byte(500) is True

    def test_contains_byte_start_inclusive(self):
        assert self.part.contains_byte(0) is True

    def test_contains_byte_end_exclusive(self):
        assert self.part.contains_byte(1000) is False

    def test_contains_byte_before_part(self):
        assert self.part.contains_byte(-1) is False

    def test_contains_byte_after_part(self):
        assert self.part.contains_byte(1001) is False

    def test_local_offset_calculation(self):
        part = make_part(2, 1000, 2000)
        assert part.local_offset(1500) == 500

    def test_local_offset_at_start(self):
        part = make_part(3, 1000, 2000)
        assert part.local_offset(1000) == 0


# ---------------------------------------------------------------------------
# TestStreamChunkMath — replicate download.py formulas and assert correctness
# ---------------------------------------------------------------------------


class TestStreamChunkMath:
    """Validates the chunk-offset formulas from download.py lines 41-45."""

    C = PYROGRAM_CHUNK_SIZE  # 1_048_576

    def chunk_math(self, offset, length):
        C = self.C
        chunk_off = offset // C
        skip = offset % C
        total = (length + skip + C - 1) // C
        return chunk_off, skip, total

    def test_at_zero_boundary(self):
        assert self.chunk_math(0, 100) == (0, 0, 1)

    def test_mid_chunk_offset(self):
        assert self.chunk_math(512 * 1024, 100) == (0, 524288, 1)

    def test_exact_chunk_boundary(self):
        assert self.chunk_math(self.C, 100) == (1, 0, 1)

    def test_spanning_two_chunks(self):
        assert self.chunk_math(0, self.C + 1) == (0, 0, 2)

    def test_spanning_with_skip(self):
        # skip=C//2 bytes consumed from first chunk, so two chunks needed
        assert self.chunk_math(self.C // 2, self.C) == (0, self.C // 2, 2)

    def test_large_offset(self):
        assert self.chunk_math(5 * self.C, self.C) == (5, 0, 1)


# ---------------------------------------------------------------------------
# TestVirtualStreamReaderInit
# ---------------------------------------------------------------------------


class TestVirtualStreamReaderInit:
    """VirtualStreamReader.__init__ — sorting and size aggregation."""

    def test_init_sorts_parts_by_index(self):
        p0 = make_part(0, 0, 1024 * 1024, part_index=0)
        p1 = make_part(1, 1024 * 1024, 2 * 1024 * 1024, part_index=1)
        p2 = make_part(2, 2 * 1024 * 1024, 3 * 1024 * 1024, part_index=2)
        reader = make_reader([p2, p1, p0])  # intentionally reversed
        assert [p.part_index for p in reader._parts] == [0, 1, 2]

    def test_init_calculates_total_size(self):
        p0 = make_part(0, 0, 1024 * 1024)
        p1 = make_part(1, 1024 * 1024, 2 * 1024 * 1024)
        reader = make_reader([p0, p1])
        assert reader.total_size == 2 * 1024 * 1024

    def test_init_single_part(self):
        p0 = make_part(0, 0, 5 * 1024 * 1024)
        reader = make_reader([p0])
        assert reader.total_size == 5 * 1024 * 1024

    def test_init_empty_parts(self):
        reader = make_reader([])
        assert reader.total_size == 0


# ---------------------------------------------------------------------------
# TestFindPartForOffset
# ---------------------------------------------------------------------------


class TestFindPartForOffset:
    """VirtualStreamReader._find_part_for_offset() — boundary math."""

    MB = 1024 * 1024

    def setup_method(self):
        self.part0 = make_part(0, 0, self.MB)
        self.part1 = make_part(1, self.MB, 2 * self.MB)
        self.reader = make_reader([self.part0, self.part1])

    def test_finds_first_part_at_offset_zero(self):
        pos = self.reader._find_part_for_offset(0)
        assert pos is not None
        assert pos.part is self.part0
        assert pos.local_offset == 0

    def test_finds_first_part_at_last_byte(self):
        pos = self.reader._find_part_for_offset(self.MB - 1)
        assert pos is not None
        assert pos.part is self.part0

    def test_finds_second_part_at_boundary(self):
        pos = self.reader._find_part_for_offset(self.MB)
        assert pos is not None
        assert pos.part is self.part1
        assert pos.local_offset == 0

    def test_finds_second_part_at_last_byte(self):
        pos = self.reader._find_part_for_offset(2 * self.MB - 1)
        assert pos is not None
        assert pos.part is self.part1

    def test_returns_none_for_negative(self):
        assert self.reader._find_part_for_offset(-1) is None

    def test_returns_none_for_total_size(self):
        assert self.reader._find_part_for_offset(2 * self.MB) is None

    def test_returns_none_for_overflow(self):
        assert self.reader._find_part_for_offset(2 * self.MB + 100) is None


# ---------------------------------------------------------------------------
# TestReadRangeByteCalculations
# ---------------------------------------------------------------------------


class TestReadRangeByteCalculations:
    """read_range() — clamping, part dispatch, and client round-robin."""

    MB = 1024 * 1024

    @pytest.fixture
    def patched_reader(self, mocker):
        """Reader with all Telegram/worker side-effects mocked out."""
        part0 = make_part(0, 0, self.MB)
        part1 = make_part(1, self.MB, 2 * self.MB)
        reader = make_reader([part0, part1])
        mock_client = MagicMock()

        mocker.patch(
            "app.services.streaming.reader.worker_manager.get_available_clients",
            new_callable=AsyncMock,
            return_value=[mock_client],
        )
        mocker.patch("app.services.streaming.reader.worker_manager.release_clients")
        mocker.patch(
            "app.services.streaming.reader.worker_manager.pool_pressure",
            return_value=0.0,
        )
        mocker.patch(
            "app.services.streaming.reader.worker_manager.try_acquire_one",
            new_callable=AsyncMock,
            return_value=None,
        )
        mocker.patch(
            "app.services.streaming.reader.refresh_all_file_ids",
            new_callable=AsyncMock,
        )
        mocker.patch(
            "app.services.streaming.reader.ensure_file_ids_for_client",
            new_callable=AsyncMock,
        )

        return reader, mock_client, part0, part1

    async def _collect(self, gen):
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)
        return b"".join(chunks)

    async def test_clamps_negative_start(self, mocker, patched_reader):
        reader, mock_client, part0, part1 = patched_reader
        calls = []

        async def capturing_stream_part(client, part, offset, length, *, is_force_released):
            calls.append((part.part_index, offset, length))
            yield b"x" * length

        mocker.patch("app.services.streaming.reader.stream_part", new=capturing_stream_part)

        data = await self._collect(reader.read_range(-100))
        assert len(data) > 0
        assert calls[0][1] == 0  # first call offset clamped to 0

    async def test_clamps_end_beyond_total(self, mocker, patched_reader):
        reader, mock_client, part0, part1 = patched_reader
        total_size = reader.total_size

        async def mock_stream_part(client, part, offset, length, *, is_force_released):
            yield b"x" * length

        mocker.patch("app.services.streaming.reader.stream_part", new=mock_stream_part)

        data = await self._collect(reader.read_range(0, total_size + 9999))
        assert len(data) == total_size

    async def test_empty_range_yields_nothing(self, patched_reader):
        reader, *_ = patched_reader
        data = await self._collect(reader.read_range(500, 500))
        assert data == b""

    async def test_start_equals_end_yields_nothing(self, patched_reader):
        reader, *_ = patched_reader
        data = await self._collect(reader.read_range(100, 100))
        assert data == b""

    async def test_single_part_full_read(self, mocker, patched_reader):
        reader, mock_client, part0, part1 = patched_reader
        calls = []

        async def capturing_stream_part(client, part, offset, length, *, is_force_released):
            calls.append((part.part_index, offset, length))
            yield b"x" * length

        mocker.patch("app.services.streaming.reader.stream_part", new=capturing_stream_part)

        data = await self._collect(reader.read_range(0, self.MB))
        assert len(calls) == 1
        assert calls[0] == (0, 0, self.MB)

    async def test_single_part_partial_read(self, mocker, patched_reader):
        reader, mock_client, part0, part1 = patched_reader
        calls = []

        async def capturing_stream_part(client, part, offset, length, *, is_force_released):
            calls.append((part.part_index, offset, length))
            yield b"x" * length

        mocker.patch("app.services.streaming.reader.stream_part", new=capturing_stream_part)

        data = await self._collect(reader.read_range(100, 900))
        assert len(calls) == 1
        assert calls[0] == (0, 100, 800)

    async def test_cross_part_boundary_calls_two_parts(self, mocker, patched_reader):
        reader, mock_client, part0, part1 = patched_reader
        calls = []

        async def capturing_stream_part(client, part, offset, length, *, is_force_released):
            calls.append(part.part_index)
            yield b"x" * length

        mocker.patch("app.services.streaming.reader.stream_part", new=capturing_stream_part)

        # Read spans from 512KB (in part0) to 1MB+512KB (in part1)
        await self._collect(reader.read_range(self.MB // 2, self.MB + self.MB // 2))
        assert len(calls) == 2

    async def test_cross_part_correct_offsets(self, mocker, patched_reader):
        reader, mock_client, part0, part1 = patched_reader
        calls = []

        async def capturing_stream_part(client, part, offset, length, *, is_force_released):
            calls.append((part.part_index, offset, length))
            yield b"x" * length

        mocker.patch("app.services.streaming.reader.stream_part", new=capturing_stream_part)

        half = self.MB // 2
        await self._collect(reader.read_range(half, self.MB + half))

        assert calls[0] == (0, half, half)   # part0: local_offset=512KB, length=512KB
        assert calls[1] == (1, 0, half)       # part1: local_offset=0, length=512KB

    async def test_active_streams_incremented_and_decremented(self, mocker, patched_reader):
        reader, mock_client, part0, part1 = patched_reader
        active_during = []

        async def capturing_stream_part(client, part, offset, length, *, is_force_released):
            active_during.append(reader._active_streams)
            yield b"x" * length

        mocker.patch("app.services.streaming.reader.stream_part", new=capturing_stream_part)

        await self._collect(reader.read_range(0, 100))
        assert active_during[0] == 1  # counter incremented during streaming
        assert reader._active_streams == 0  # decremented after completion

    async def test_round_robin_client_used(self, mocker, patched_reader):
        reader, mock_client, part0, part1 = patched_reader
        mock_client2 = MagicMock()

        # Inject two clients directly; persistent=True keeps them between calls
        reader._clients = [mock_client, mock_client2]
        reader._persistent = True

        used_clients = []

        async def capturing_stream_part(client, part, offset, length, *, is_force_released):
            used_clients.append(client)
            yield b"x" * length

        mocker.patch("app.services.streaming.reader.stream_part", new=capturing_stream_part)

        await self._collect(reader.read_range(0, 100))
        await self._collect(reader.read_range(0, 100))

        assert used_clients[0] is mock_client   # rr_counter=0 → clients[0]
        assert used_clients[1] is mock_client2  # rr_counter=1 → clients[1]


# ---------------------------------------------------------------------------
# TestChunkCache
# ---------------------------------------------------------------------------


class TestChunkCache:
    """Direct tests on cache.py — store, retrieve, TTL, eviction, invalidation."""

    def test_store_and_retrieve(self):
        _cache_chunk(1, 0, b"hello")
        assert _get_cached_chunk(1, 0) == b"hello"

    def test_miss_returns_none(self):
        assert _get_cached_chunk(99, 0) is None

    def test_chunk_expired_returns_none(self, mocker):
        _cache_chunk(1, 0, b"data")
        future_time = time.time() + cache_module._CHUNK_CACHE_TTL + 1
        mocker.patch("app.services.streaming.cache.time.time", return_value=future_time)
        assert _get_cached_chunk(1, 0) is None

    def test_lru_eviction(self):
        for i in range(cache_module._CHUNK_CACHE_MAX_SIZE + 1):
            _cache_chunk(i, 0, b"data")
        assert len(cache_module._CHUNK_CACHE) == cache_module._CHUNK_CACHE_MAX_SIZE

    def test_invalidate_specific_client(self):
        cache_module._FILE_ID_CACHE[(1, 42)] = ("fid", time.time())
        invalidate_file_id_cache(1, client_id=42)
        assert (1, 42) not in cache_module._FILE_ID_CACHE

    def test_invalidate_all_clients_for_part(self):
        cache_module._FILE_ID_CACHE[(1, 42)] = ("fid", time.time())
        cache_module._FILE_ID_CACHE[(1, 99)] = ("fid", time.time())
        cache_module._FILE_ID_CACHE[1] = ("fid", time.time())
        invalidate_file_id_cache(1)
        assert (1, 42) not in cache_module._FILE_ID_CACHE
        assert (1, 99) not in cache_module._FILE_ID_CACHE
        assert 1 not in cache_module._FILE_ID_CACHE

    def test_invalidate_leaves_other_parts(self):
        cache_module._FILE_ID_CACHE[(1, 42)] = ("fid", time.time())
        cache_module._FILE_ID_CACHE[(2, 42)] = ("fid", time.time())
        invalidate_file_id_cache(1)
        assert (2, 42) in cache_module._FILE_ID_CACHE


# ---------------------------------------------------------------------------
# TestManagerGetVirtualReader
# ---------------------------------------------------------------------------


class TestManagerGetVirtualReader:
    """get_virtual_reader / release_reader / cleanup_stale_readers — real SQLite DB."""

    @pytest_asyncio.fixture
    async def media_with_parts(self, test_session):
        """Insert a real MediaItem + MediaPart row into the test SQLite DB."""
        media = MediaItem(
            title="Test Film",
            media_type=MediaType.MOVIE,
            duration_seconds=5400,
        )
        test_session.add(media)
        await test_session.flush()

        part = MediaPart(
            media_item_id=media.id,
            telegram_file_id="fid_abc",
            part_index=0,
            start_byte=0,
            end_byte=1_048_576,
            file_size=1_048_576,
            channel_id=100,
            topic_id=None,
            message_id=1001,
        )
        test_session.add(part)
        await test_session.commit()
        return media, part

    async def test_returns_none_for_missing_media(self, test_session):
        result = await get_virtual_reader(test_session, 99999)
        assert result is None

    async def test_returns_reader_for_existing_media(self, test_session, media_with_parts):
        media, part = media_with_parts
        reader = await get_virtual_reader(test_session, media.id)
        assert reader is not None
        assert isinstance(reader, VirtualStreamReader)
        assert reader.total_size == 1_048_576

    async def test_persistent_reader_is_cached(self, test_session, media_with_parts):
        media, part = media_with_parts
        reader1 = await get_virtual_reader(test_session, media.id, persistent=True)
        reader2 = await get_virtual_reader(test_session, media.id, persistent=True)
        assert reader1 is reader2

    async def test_non_persistent_not_cached(self, test_session, media_with_parts):
        media, part = media_with_parts
        reader1 = await get_virtual_reader(test_session, media.id, persistent=False)
        reader2 = await get_virtual_reader(test_session, media.id, persistent=False)
        assert reader1 is not reader2
        assert manager_module._reader_cache == {}

    async def test_release_reader_clears_cache(self, mocker, test_session, media_with_parts):
        media, part = media_with_parts
        mocker.patch("app.services.streaming.manager.worker_manager.release_clients")

        reader = await get_virtual_reader(test_session, media.id, persistent=True)
        assert media.id in manager_module._reader_cache

        await release_reader(media.id)

        assert media.id not in manager_module._reader_cache
        assert reader._force_released is True

    async def test_cleanup_removes_stale_reader(self, mocker, test_session, media_with_parts):
        media, part = media_with_parts
        mocker.patch("app.services.streaming.manager.worker_manager.release_clients")

        reader = await get_virtual_reader(test_session, media.id, persistent=True)

        # Backdate last_access by 2 minutes to make the reader stale
        manager_module._reader_cache[media.id] = (reader, time.time() - 120)

        await cleanup_stale_readers()

        assert media.id not in manager_module._reader_cache
