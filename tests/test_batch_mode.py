"""Tests for VirtualStreamReader.batch_mode() — client acquisition invariants.

WHY THIS MATTERS
----------------
The subtitle extraction pipeline calls reader.read_range() many times
(one per 10 MB cluster chunk, or up to 20 parallel cluster fetches).
Without batch_mode each call would:
  1. Call worker_manager.get_available_clients()   ← re-acquire client
  2. Call refresh_all_file_ids()                   ← re-refresh file_ids
  3. Make the Telegram download request
  4. Call worker_manager.release_clients()         ← release client

Step 1+2 on rapid succession can trigger Telegram FloodWait and/or race
against file_id expiry.  batch_mode pins one client for the lifetime of
the extraction, reducing those operations to a single pair at entry/exit.

INVARIANTS UNDER TEST
---------------------
  A. get_available_clients  called ONCE at batch_mode entry, not per read
  B. release_clients        called ZERO times during reads, ONCE on exit
  C. refresh_all_file_ids   called ONCE at batch_mode entry, not per read
  D. _batch_mode_active     True inside context, False after exit
  E. nested batch_mode      is a no-op (idempotent, no double-acquire)
  F. ensure_file_ids_for_client  still called per read (client-local cache)
  CONTRAST:
  G. without batch_mode     get_available_clients + release_clients each read
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaPart
from app.services.streaming.reader import VirtualStreamReader


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def make_part(part_id: int, start: int, end: int) -> MediaPart:
    return MediaPart(
        id=part_id,
        media_item_id=1,
        telegram_file_id=f"file_id_{part_id}",
        part_index=part_id,
        start_byte=start,
        end_byte=end,
        file_size=end - start,
        channel_id=100,
        topic_id=None,
        message_id=part_id * 10,
    )


def make_reader(*parts: MediaPart) -> VirtualStreamReader:
    media = MagicMock(spec=MediaItem)
    media.id = 1
    media.parts = list(parts)
    media.duration_seconds = None
    session = MagicMock(spec=AsyncSession)
    return VirtualStreamReader(media_item=media, session=session)


# ─────────────────────────────────────────────────────────────────────────────
# Patch context — everything that touches Telegram / the worker pool
# ─────────────────────────────────────────────────────────────────────────────


class Patches:
    """Holds all mocks injected into VirtualStreamReader for one test."""

    def __init__(
        self,
        get_clients,
        release_clients,
        pool_pressure,
        try_acquire_one,
        refresh_all_file_ids,
        ensure_file_ids,
    ):
        self.get_clients = get_clients
        self.release_clients = release_clients
        self.pool_pressure = pool_pressure
        self.try_acquire_one = try_acquire_one
        self.refresh_all_file_ids = refresh_all_file_ids
        self.ensure_file_ids = ensure_file_ids


@pytest.fixture()
def mock_client():
    return MagicMock(name="pyrogram_client")


@pytest.fixture()
def patches(mock_client):
    """Patch all external Telegram/pool dependencies at the reader module level."""
    # stream_part: async generator that yields 100 bytes for the requested length
    async def fake_stream_part(client, part, offset, length, *, is_force_released):
        yield b"x" * length

    with (
        patch(
            "app.services.streaming.reader.worker_manager.get_available_clients",
            new=AsyncMock(return_value=[mock_client]),
        ) as get_clients,
        patch(
            "app.services.streaming.reader.worker_manager.release_clients",
        ) as release_clients,
        patch(
            "app.services.streaming.reader.worker_manager.pool_pressure",
            return_value=0.0,
        ) as pool_pressure,
        patch(
            "app.services.streaming.reader.worker_manager.try_acquire_one",
            new=AsyncMock(return_value=None),
        ) as try_acquire_one,
        patch(
            "app.services.streaming.reader.refresh_all_file_ids",
            new=AsyncMock(),
        ) as refresh_all,
        patch(
            "app.services.streaming.reader.ensure_file_ids_for_client",
            new=AsyncMock(),
        ) as ensure_ids,
        patch(
            "app.services.streaming.reader.stream_part",
            new=fake_stream_part,
        ),
    ):
        yield Patches(
            get_clients=get_clients,
            release_clients=release_clients,
            pool_pressure=pool_pressure,
            try_acquire_one=try_acquire_one,
            refresh_all_file_ids=refresh_all,
            ensure_file_ids=ensure_ids,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Invariant A — get_available_clients called once, not per read
# ─────────────────────────────────────────────────────────────────────────────


class TestSingleClientAcquisition:
    async def test_get_clients_called_once_at_entry(self, patches):
        """Entering batch_mode acquires clients exactly once."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            assert patches.get_clients.call_count == 1

    async def test_get_clients_not_called_again_per_read_range(self, patches):
        """Each read_range inside batch_mode does NOT re-acquire clients."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            async for _ in reader.read_range(0, 100):
                pass
            async for _ in reader.read_range(0, 100):
                pass
            async for _ in reader.read_range(0, 100):
                pass
        assert patches.get_clients.call_count == 1  # still just the one at entry


# ─────────────────────────────────────────────────────────────────────────────
# Invariant B — release_clients: zero during reads, one on exit
# ─────────────────────────────────────────────────────────────────────────────


class TestClientRelease:
    async def test_no_release_between_reads(self, patches):
        """release_clients must not be called while batch_mode is active."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            async for _ in reader.read_range(0, 100):
                pass
            assert patches.release_clients.call_count == 0  # not released yet

            async for _ in reader.read_range(0, 100):
                pass
            assert patches.release_clients.call_count == 0  # still not released

    async def test_clients_released_exactly_once_on_exit(self, patches):
        """batch_mode releases clients exactly once when the context exits."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            async for _ in reader.read_range(0, 100):
                pass
            async for _ in reader.read_range(0, 100):
                pass

        assert patches.release_clients.call_count == 1

    async def test_clients_released_even_on_exception(self, patches):
        """batch_mode releases clients even if an exception escapes the block."""
        reader = make_reader(make_part(1, 0, 100))
        with pytest.raises(RuntimeError):
            async with reader.batch_mode():
                raise RuntimeError("simulated failure")

        assert patches.release_clients.call_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Invariant C — refresh_all_file_ids once at entry, not per read
# ─────────────────────────────────────────────────────────────────────────────


class TestFileIdRefresh:
    async def test_refresh_called_once_at_batch_mode_entry(self, patches):
        """refresh_all_file_ids is called once when batch_mode starts."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            assert patches.refresh_all_file_ids.call_count == 1

    async def test_refresh_not_called_per_read_range(self, patches):
        """Three read_range calls inside batch_mode → still only one refresh."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            for _ in range(3):
                async for _ in reader.read_range(0, 100):
                    pass

        assert patches.refresh_all_file_ids.call_count == 1

    async def test_ensure_file_ids_still_called_per_read(self, patches):
        """ensure_file_ids_for_client IS still called per read_range (client cache)."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            for _ in range(3):
                async for _ in reader.read_range(0, 100):
                    pass

        # Called once per read_range (not zero, not once for the whole batch)
        assert patches.ensure_file_ids.call_count == 3


# ─────────────────────────────────────────────────────────────────────────────
# Invariant D — _batch_mode_active flag transitions
# ─────────────────────────────────────────────────────────────────────────────


class TestBatchModeFlag:
    async def test_flag_false_before_entry(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        assert reader._batch_mode_active is False

    async def test_flag_true_inside_context(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            assert reader._batch_mode_active is True

    async def test_flag_false_after_normal_exit(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            pass
        assert reader._batch_mode_active is False

    async def test_flag_false_after_exception(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        with pytest.raises(RuntimeError):
            async with reader.batch_mode():
                raise RuntimeError("boom")
        assert reader._batch_mode_active is False


# ─────────────────────────────────────────────────────────────────────────────
# Invariant E — nested batch_mode is idempotent
# ─────────────────────────────────────────────────────────────────────────────


class TestNestedBatchMode:
    async def test_nested_entry_does_not_re_acquire_clients(self, patches):
        """Inner batch_mode() is a no-op: no extra get_available_clients call."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():           # outer
            async with reader.batch_mode():       # inner — should be no-op
                assert patches.get_clients.call_count == 1

    async def test_nested_entry_does_not_re_refresh_file_ids(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            async with reader.batch_mode():
                assert patches.refresh_all_file_ids.call_count == 1

    async def test_inner_exit_does_not_release_clients(self, patches):
        """Exiting the inner context manager does NOT release the client."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            async with reader.batch_mode():
                pass
            # After inner exit, still inside outer → clients still held
            assert patches.release_clients.call_count == 0

    async def test_outer_exit_releases_clients_once(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            async with reader.batch_mode():
                pass
        assert patches.release_clients.call_count == 1

    async def test_flag_stays_true_after_inner_exit(self, patches):
        """_batch_mode_active remains True until the outermost context exits."""
        reader = make_reader(make_part(1, 0, 100))
        async with reader.batch_mode():
            async with reader.batch_mode():
                pass
            assert reader._batch_mode_active is True  # outer still active


# ─────────────────────────────────────────────────────────────────────────────
# Invariant G — CONTRAST: without batch_mode, acquire/release per read
# ─────────────────────────────────────────────────────────────────────────────


class TestWithoutBatchMode:
    """Document the per-read acquire/release cycle that batch_mode avoids.

    This is the behaviour that causes the Telegram FloodWait risk when
    the subtitle pipeline makes many rapid requests without batch_mode.
    """

    async def test_get_clients_called_per_read_outside_batch_mode(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        for _ in range(3):
            async for _ in reader.read_range(0, 100):
                pass
        # Each read re-acquires because the previous read released the client
        assert patches.get_clients.call_count == 3

    async def test_release_clients_called_per_read_outside_batch_mode(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        for _ in range(3):
            async for _ in reader.read_range(0, 100):
                pass
        assert patches.release_clients.call_count == 3

    async def test_refresh_file_ids_called_per_read_outside_batch_mode(self, patches):
        reader = make_reader(make_part(1, 0, 100))
        for _ in range(3):
            async for _ in reader.read_range(0, 100):
                pass
        # refresh_all_file_ids on every read — wasted round-trips to Telegram
        assert patches.refresh_all_file_ids.call_count == 3

    async def test_batch_mode_reduces_overhead_by_n_minus_1(self, patches):
        """
        For N reads, batch_mode does 1 acquire+refresh instead of N.
        This directly represents the reduction in Telegram API calls
        that could otherwise trigger FloodWait or race file_id expiry.
        """
        N = 10
        reader_batch = make_reader(make_part(1, 0, 100))
        async with reader_batch.batch_mode():
            for _ in range(N):
                async for _ in reader_batch.read_range(0, 100):
                    pass

        batch_acquires = patches.get_clients.call_count
        batch_refreshes = patches.refresh_all_file_ids.call_count

        # Reset mock counters for the non-batch comparison
        patches.get_clients.reset_mock()
        patches.refresh_all_file_ids.reset_mock()

        reader_plain = make_reader(make_part(1, 0, 100))
        for _ in range(N):
            async for _ in reader_plain.read_range(0, 100):
                pass

        plain_acquires = patches.get_clients.call_count
        plain_refreshes = patches.refresh_all_file_ids.call_count

        assert batch_acquires == 1
        assert batch_refreshes == 1
        assert plain_acquires == N      # N times more acquire calls
        assert plain_refreshes == N     # N times more refresh calls
