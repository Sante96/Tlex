"""Real integration tests for VirtualStreamReader.batch_mode().

These tests hit the real PostgreSQL database and the real Telegram API.
No mocking.  They skip automatically if the infrastructure is not available.

PREREQUISITES
-------------
  1. Running PostgreSQL (configured in .env)
  2. At least one ACTIVE Worker record with a valid session_string
  3. At least one MediaItem with associated MediaParts

RUN
---
  uv run pytest -m integration -s -v

WHAT IS TESTED
--------------
  A. The Pyrogram client is marked as IN_USE in the pool during batch_mode
     and returned to AVAILABLE immediately after exit.

  B. The exact same client object is used for all read_range calls inside
     batch_mode — no release-and-re-acquire between reads.

  C. Actual bytes are downloaded from Telegram (content is non-empty).

  D. Without batch_mode, each read re-acquires from the pool: the client is
     released after every read_range call and re-acquired for the next one.

  E. batch_mode is faster than repeated independent reads because it skips
     the acquire/release/refresh cycle between calls.
"""

import asyncio
import time

import pytest
import pytest_asyncio

# All tests in this module share the module-level event loop so that
# the Pyrogram clients started by the module-scoped fixtures are usable
# inside every test function without "Future attached to a different loop".
pytestmark = pytest.mark.asyncio(loop_scope="module")
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, selectinload

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.models.media import MediaItem
from app.services.streaming.reader import VirtualStreamReader


# ─────────────────────────────────────────────────────────────────────────────
# NOTE ON LOOP SCOPE
# ─────────────────────────────────────────────────────────────────────────────
# Pyrogram clients must be started and used on the same event loop.
# We use loop_scope="module" on every async fixture so that all fixtures and
# all tests in this module share one event loop for their lifetime.
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def real_session():
    """Open a real async session to the production PostgreSQL database."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))  # connectivity check
            yield session
    except Exception as e:
        pytest.skip(f"PostgreSQL not reachable: {e}")
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def loaded_workers(real_session):
    """Load real Pyrogram workers. Skip if none available."""
    if not worker_manager._client_pool:
        try:
            count = await worker_manager.load_workers(real_session)
        except Exception as e:
            pytest.skip(f"Failed to load workers: {e}")
        if count == 0:
            pytest.skip("No active workers in the database")

    yield worker_manager

    await worker_manager.shutdown()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def small_media_item(real_session, loaded_workers):
    """Pick the MediaItem with the fewest/smallest parts to minimise Telegram traffic."""
    query = (
        select(MediaItem)
        .options(selectinload(MediaItem.parts))
        .order_by(MediaItem.id)
        .limit(50)
    )
    result = await real_session.execute(query)
    items = result.scalars().all()

    candidates = [m for m in items if m.parts]
    if not candidates:
        pytest.skip("No MediaItems with parts found")

    return min(candidates, key=lambda m: sum(p.file_size for p in m.parts))


@pytest_asyncio.fixture(loop_scope="module")
async def reader(small_media_item, real_session):
    """Fresh VirtualStreamReader for each test (shares module event loop)."""
    return VirtualStreamReader(media_item=small_media_item, session=real_session)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

READ_BYTES = 4 * 1024   # 4 KB per read — minimal Telegram traffic
N_READS    = 3


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def pool_in_use_count() -> int:
    return sum(1 for v in worker_manager._client_in_use.values() if v)

def client_is_in_use(client) -> bool:
    return worker_manager._client_in_use.get(id(client), False)


# ─────────────────────────────────────────────────────────────────────────────
# A. Client marked IN_USE during batch_mode, AVAILABLE after exit
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestPoolStateWithRealWorkers:

    async def test_client_in_use_during_batch_mode(self, reader):
        """
        After entering batch_mode, the acquired client must be marked in_use
        in the worker pool — preventing other streams from stealing it.
        """
        in_use_before = pool_in_use_count()

        async with reader.batch_mode():
            assert reader._clients, "batch_mode must acquire at least one client"
            client = reader._clients[0]

            assert client_is_in_use(client), (
                "Client is NOT marked in_use in the pool during batch_mode — "
                "another concurrent stream could steal it mid-extraction"
            )
            assert pool_in_use_count() == in_use_before + len(reader._clients)

        assert not client_is_in_use(client), "Client still in_use after exit — pool leak!"
        assert pool_in_use_count() == in_use_before

    async def test_client_not_acquired_before_batch_mode(self, reader):
        assert not reader._clients
        assert reader._batch_mode_active is False


# ─────────────────────────────────────────────────────────────────────────────
# B. Same client object across all reads inside batch_mode
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestClientStabilityAcrossReads:

    async def test_same_client_used_for_all_reads(self, reader):
        """
        Every read_range inside batch_mode must use the same Pyrogram client.
        A changing id() means release-and-re-acquire occurred — which risks
        FloodWait and exposes the file_id to race conditions.
        """
        total_size = reader.total_size
        client_ids: list[int] = []

        async with reader.batch_mode():
            initial_id = id(reader._clients[0])

            for i in range(N_READS):
                start = min(i * READ_BYTES, total_size - 1)
                end   = min(start + READ_BYTES, total_size)
                async for _ in reader.read_range(start, end):
                    pass
                client_ids.append(id(reader._clients[0]))

        assert all(cid == initial_id for cid in client_ids), (
            f"Client changed between reads: {client_ids} — "
            "batch_mode is not pinning the client correctly"
        )

    async def test_client_list_not_recreated_between_reads(self, reader):
        """reader._clients must be the same list object throughout batch_mode."""
        total_size = reader.total_size

        async with reader.batch_mode():
            list_id = id(reader._clients)
            for i in range(N_READS):
                start = min(i * READ_BYTES, total_size - 1)
                end   = min(start + READ_BYTES, total_size)
                async for _ in reader.read_range(start, end):
                    pass
                assert id(reader._clients) == list_id


# ─────────────────────────────────────────────────────────────────────────────
# C. Actual bytes downloaded from Telegram
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestRealDownload:

    async def test_bytes_received_inside_batch_mode(self, reader):
        """Download the first 4 KB inside batch_mode — must return real data."""
        received = bytearray()
        end = min(READ_BYTES, reader.total_size)

        async with reader.batch_mode():
            async for chunk in reader.read_range(0, end):
                received.extend(chunk)

        assert len(received) > 0, "No bytes received from Telegram"
        assert len(received) == end, f"Expected {end} B, got {len(received)} B"

    async def test_same_range_twice_returns_identical_bytes(self, reader):
        """
        The same 4 KB range read twice in batch_mode must return identical bytes.
        A mismatch means the Pyrogram session state was corrupted between reads.
        """
        end = min(READ_BYTES, reader.total_size)

        async with reader.batch_mode():
            first = bytearray()
            async for chunk in reader.read_range(0, end):
                first.extend(chunk)

            second = bytearray()
            async for chunk in reader.read_range(0, end):
                second.extend(chunk)

        assert first == second, (
            "Two reads of the same range returned different bytes — "
            "Pyrogram connection state was corrupted inside batch_mode"
        )

    async def test_sequential_reads_equal_single_read(self, reader):
        """
        N non-overlapping reads concatenated must equal one read of the total range.
        Proves that byte offsets are computed correctly across reads in batch_mode.
        """
        total_size  = reader.total_size
        chunk_size  = min(READ_BYTES, total_size // (N_READS + 1) or 1)
        total_end   = min(chunk_size * N_READS, total_size)

        # Reference: single read
        reference = bytearray()
        async with reader.batch_mode():
            async for chunk in reader.read_range(0, total_end):
                reference.extend(chunk)

        # N sequential reads
        combined = bytearray()
        async with reader.batch_mode():
            for i in range(N_READS):
                start = i * chunk_size
                end   = min(start + chunk_size, total_end)
                if start >= total_end:
                    break
                async for chunk in reader.read_range(start, end):
                    combined.extend(chunk)

        assert bytes(combined) == bytes(reference), (
            "Sequential reads inside batch_mode don't reconstruct the same data — "
            "seek/offset handling is broken"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D. Contrast: without batch_mode, each read independently acquires/releases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestPoolBehaviourWithoutBatchMode:

    async def test_pool_returns_to_baseline_after_each_read(self, reader):
        """
        Without batch_mode the pool in_use count must drop to baseline after
        every read_range — confirming the per-read acquire/release cycle.
        """
        baseline = pool_in_use_count()
        end = min(READ_BYTES, reader.total_size)

        for _ in range(N_READS):
            async for _ in reader.read_range(0, end):
                pass
            assert pool_in_use_count() == baseline, (
                "Client not released after read_range outside batch_mode"
            )

    async def test_clients_cleared_between_independent_reads(self, reader):
        """
        Between two non-batch reads, reader._clients must be empty —
        cleared by _release_workers, so the next read must re-acquire.
        """
        end = min(READ_BYTES, reader.total_size)
        async for _ in reader.read_range(0, end):
            pass
        assert not reader._clients, (
            "reader._clients not empty after standalone read_range — "
            "_release_workers did not clear the list"
        )


# ─────────────────────────────────────────────────────────────────────────────
# E. batch_mode is measurably faster for repeated reads
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestBatchModePerformance:

    async def test_batch_mode_faster_than_independent_reads(
        self, small_media_item, real_session
    ):
        """
        batch_mode must complete N reads faster than N independent reads
        because it eliminates N-1 acquire/refresh_all_file_ids/release cycles.

        A 20% margin accounts for measurement noise on slow connections.
        The real gap in production is 5-10× because each refresh_all_file_ids
        involves at least one Telegram MTProto round-trip.
        """
        N   = 5
        end = min(READ_BYTES, 1)  # use 1 byte per read to isolate overhead

        # Read total_size from a fresh reader first
        probe = VirtualStreamReader(media_item=small_media_item, session=real_session)
        end = min(READ_BYTES, probe.total_size)

        reader_batch = VirtualStreamReader(media_item=small_media_item, session=real_session)
        reader_plain = VirtualStreamReader(media_item=small_media_item, session=real_session)

        # Warm up: one read each to populate file_id cache
        async with reader_batch.batch_mode():
            async for _ in reader_batch.read_range(0, end):
                pass
        async for _ in reader_plain.read_range(0, end):
            pass

        # Measure batch_mode: N reads in a single context
        t0 = time.perf_counter()
        async with reader_batch.batch_mode():
            for _ in range(N):
                async for _ in reader_batch.read_range(0, end):
                    pass
        time_batch = time.perf_counter() - t0

        # Measure independent: N reads each with acquire/release
        t0 = time.perf_counter()
        for _ in range(N):
            async for _ in reader_plain.read_range(0, end):
                pass
        time_plain = time.perf_counter() - t0

        speedup = time_plain / time_batch if time_batch > 0 else float("inf")
        print(
            f"\n  batch_mode  : {time_batch:.3f}s for {N} reads\n"
            f"  independent : {time_plain:.3f}s for {N} reads\n"
            f"  speedup     : {speedup:.1f}×"
        )

        assert time_batch < time_plain * 0.8, (
            f"batch_mode ({time_batch:.3f}s) not significantly faster than "
            f"independent ({time_plain:.3f}s, speedup={speedup:.2f}×). "
            "The acquire/release overhead may not dominate at this file size."
        )
