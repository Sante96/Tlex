"""Virtual Stream Reader — unified file-like interface over Telegram parts."""

import asyncio
import time
import weakref
from collections import deque
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager

from loguru import logger
from pyrogram import Client

from app.core.worker_manager import MAX_CLIENTS_PER_STREAM, worker_manager
from app.models.media import MediaItem, MediaPart
from app.services.streaming.cache import FILE_ID_CACHE, PYROGRAM_CHUNK_SIZE
from app.services.streaming.download import (
    MAX_ATTEMPTS,
    SessionDown,
    Throttled,
    connected,
    fetch_chunk,
    read_small,
)
from app.services.streaming.models import StreamPosition
from app.services.streaming.telegram import (
    ensure_file_ids_for_client,
    refresh_all_file_ids,
)

IN_FLIGHT_PER_CLIENT = 4  # more requests per connection didn't add speed
MAX_IN_FLIGHT = 8  # per read: 8 MB buffered at most
SCALE_UP_BELOW = 0.5  # pool pressure (share of clients in use)
SCALE_DOWN_ABOVE = 0.75
REBALANCE_SECONDS = 5.0  # how often a long read rechecks its clients

# Readers holding clients, for _reclaim_spare_client
_readers: weakref.WeakSet["VirtualStreamReader"] = weakref.WeakSet()


def _reclaim_spare_client() -> bool:
    """With the pool exhausted, take back the extra client of the stream holding the most,
    so a new viewer gets one instead of an error. The donor's reads stop using it at their
    next chunk."""
    donor = max(
        (r for r in _readers if len(r._clients) > 1 and not r._batch_mode_active),
        key=lambda r: len(r._clients),
        default=None,
    )
    if donor is None:
        return False
    worker_manager.release_clients([donor._clients.pop()])
    logger.info(
        f"[STREAM] Reclaimed a client from a stream for a new viewer ({len(donor._clients)} left)"
    )
    return True


class VirtualStreamReader:
    """
    Reads bytes from a virtual file composed of multiple Telegram parts.

    Handles transparent concatenation of split files, seeking to any byte
    offset, seamless boundary crossing, and chunked streaming.
    """

    def __init__(self, media_item: MediaItem) -> None:
        self._media_item = media_item
        self._parts: list[MediaPart] = sorted(media_item.parts, key=lambda p: p.part_index)
        self._total_size = sum(p.file_size for p in self._parts)
        self._clients: list[Client] = []
        self._batch_mode_active = False
        self._persistent = False
        self._rr_counter = 0
        self._active_streams = 0
        self._force_released = False
        self._swap_lock = asyncio.Lock()

    @property
    def total_size(self) -> int:
        """Total size of the virtual file in bytes."""
        return self._total_size

    @property
    def duration_seconds(self) -> int | None:
        """Duration of the media in seconds."""
        return self._media_item.duration_seconds

    @property
    def media_item(self) -> MediaItem:
        """The media item being streamed."""
        return self._media_item

    # --- Part lookup ---

    def _find_part_for_offset(self, byte_offset: int) -> StreamPosition | None:
        """Find which part contains the given byte offset."""
        if byte_offset < 0 or byte_offset >= self._total_size:
            return None
        for part in self._parts:
            if part.contains_byte(byte_offset):
                return StreamPosition(part=part, local_offset=part.local_offset(byte_offset))
        return None

    # --- Batch mode ---

    @asynccontextmanager
    async def batch_mode(self):
        """Context manager for batch operations (e.g. subtitle extraction)."""
        if self._batch_mode_active:
            yield
            return

        if not await self._ensure_workers():
            raise RuntimeError("No workers available")

        await refresh_all_file_ids(self._clients, self._parts)

        self._batch_mode_active = True
        try:
            yield
        finally:
            self._batch_mode_active = False
            await self._release_workers()

    # --- Client pool management ---

    async def _ensure_workers(self) -> bool:
        """Ensure we have at least 1 worker client."""
        if self._clients:
            return True
        clients = await worker_manager.get_available_clients(limit=1)
        if not clients and _reclaim_spare_client():
            clients = await worker_manager.get_available_clients(limit=1)
        if not clients:
            logger.error("No workers available for streaming")
            return False
        self._clients = clients
        _readers.add(self)
        logger.info(f"[STREAM] Acquired {len(self._clients)} client(s) from pool")
        return True

    async def _try_scale_up(self) -> None:
        """Try to dynamically acquire one more client from the pool."""
        if len(self._clients) >= MAX_CLIENTS_PER_STREAM:
            return
        # Below scale-down's 0.75: a stream that just scaled up mustn't trip the
        # scale-down at the next rebalance and flap
        if worker_manager.pool_pressure() > SCALE_UP_BELOW:
            return

        client = await worker_manager.try_acquire_one(spread_from=self._clients)
        if client is None:
            return
        if len(self._clients) >= MAX_CLIENTS_PER_STREAM:
            worker_manager.release_clients([client])
            return

        try:
            await ensure_file_ids_for_client(self._parts, client)
            # Re-check after await: another concurrent scale-up may have already appended
            if len(self._clients) >= MAX_CLIENTS_PER_STREAM:
                worker_manager.release_clients([client])
                return
            self._clients.append(client)
            logger.info(f"[STREAM] Scale-up: now {len(self._clients)} clients")
        except Exception as e:
            logger.warning(f"Scale-up failed, releasing client: {e}")
            worker_manager.release_clients([client])

    def _try_scale_down(self) -> None:
        """Release excess clients when pool is under pressure."""
        if len(self._clients) <= 1:
            return
        pressure = worker_manager.pool_pressure()
        if pressure <= SCALE_DOWN_ABOVE:
            return
        released = self._clients.pop()
        worker_manager.release_clients([released])
        logger.info(
            f"[STREAM] Scale-down: now {len(self._clients)} clients (pool pressure {pressure:.0%})"
        )

    async def _swap_throttled(self) -> bool:
        """Every client of this stream is on an account Telegram is slowing down: trade one
        for a free client of another account, if the pool has one."""
        async with self._swap_lock:
            if any(not worker_manager.is_throttled(c) for c in self._clients):
                return True  # a concurrent fetch already swapped
            client = await worker_manager.try_acquire_one(spread_from=self._clients)
            if client is None or worker_manager.is_throttled(client):
                if client is not None:
                    worker_manager.release_clients([client])
                return False
            try:
                await ensure_file_ids_for_client(self._parts, client)
            except Exception as e:
                logger.warning(f"[STREAM] Swap failed, releasing client: {e}")
                worker_manager.release_clients([client])
                return False
            if len(self._clients) >= MAX_CLIENTS_PER_STREAM:
                worker_manager.release_clients([self._clients.pop(0)])
            self._clients.append(client)
            logger.info("[STREAM] Throttled account: moved the stream to a client of another one")
            return True

    async def _fetch(self, part: MediaPart, index: int) -> bytes:
        """One chunk on one of this stream's clients, skipping those whose account Telegram
        is slowing down or whose connection is being re-established: such a chunk moves
        to another client at once instead of waiting out the FLOOD_PREMIUM_WAIT or the
        reconnection."""
        reconnecting = 0
        while True:
            usable = [
                c for c in self._clients if not worker_manager.is_throttled(c) and connected(c)
            ]
            clients = usable or self._clients
            if not clients:
                return b""  # released: read_range stops at the force-release check
            client = clients[self._rr_counter % len(clients)]
            self._rr_counter += 1
            try:
                return await fetch_chunk(client, part, index)
            except SessionDown:
                # Next try on a connected client; with none, fetch_chunk waits for this one
                # to come back, so a stream whose connections all stay down still ends
                reconnecting += 1
                if reconnecting >= MAX_ATTEMPTS:
                    raise RuntimeError(
                        f"Failed to fetch chunk {index} of part {part.id}: no client reconnected"
                    ) from None
            except Throttled as e:
                if any(not worker_manager.is_throttled(c) for c in self._clients):
                    continue
                if await self._swap_throttled():
                    continue
                logger.warning(f"[STREAM] Every account is throttled, waiting {e.seconds}s")
                await asyncio.sleep(e.seconds)

    async def _release_workers(self) -> None:
        """Release workers back to the pool for reuse."""
        if self._batch_mode_active or self._persistent:
            return
        if self._clients:
            count = len(self._clients)
            worker_manager.release_clients(self._clients)
            logger.info(f"[STREAM] Released {count} client(s) back to pool")
        self._clients = []

    # --- Main streaming ---

    def _chunk_plan(self, start: int, end: int) -> Iterator[tuple[MediaPart, int, int, int]]:
        """(part, chunk index, bytes to skip, bytes to take) for each Telegram chunk the
        range [start, end) touches."""
        offset = start
        while offset < end:
            pos = self._find_part_for_offset(offset)
            if not pos:
                return
            skip = pos.local_offset % PYROGRAM_CHUNK_SIZE
            take = min(
                PYROGRAM_CHUNK_SIZE - skip,
                pos.part.file_size - pos.local_offset,
                end - offset,
            )
            yield pos.part, pos.local_offset // PYROGRAM_CHUNK_SIZE, skip, take
            offset += take

    async def read_window(self, start: int, end: int) -> bytes:
        """Read a small byte range (subtitle blocks) without pulling whole 1 MB chunks.

        Uses read_small with a client that already has a file_id for the part (batch_mode
        refreshes one); anything it can't do — no such client, a range across parts, no
        media session yet, CDN, an expired file reference — goes through read_range, which
        handles all of those.
        """
        pos = self._find_part_for_offset(start)
        if pos and self._clients and pos.local_offset + (end - start) <= pos.part.file_size:
            client = self._clients[self._rr_counter % len(self._clients)]
            self._rr_counter += 1
            cached = FILE_ID_CACHE.get((pos.part.id, id(client)))
            if cached:
                try:
                    data = await read_small(client, cached[0], pos.local_offset, end - start)
                    if data is not None:
                        return data
                except Exception as e:
                    logger.debug(f"[STREAM] Small read fell back to chunk read: {e}")
        return b"".join([chunk async for chunk in self.read_range(start, end)])

    async def read_range(self, start: int, end: int | None = None) -> AsyncGenerator[bytes]:
        """
        Read a range of bytes from the virtual stream.

        Yields chunks of bytes for the requested range, handling part boundaries
        and fetching data from Telegram transparently.
        """
        if end is None:
            end = self._total_size
        start = max(0, start)
        end = min(end, self._total_size)
        if start >= end:
            return

        self._active_streams += 1
        pending: deque[tuple[asyncio.Task, int, int]] = deque()
        try:
            if not self._batch_mode_active:
                if not await self._ensure_workers():
                    raise RuntimeError("No workers available")
                await refresh_all_file_ids(self._clients, self._parts)

            if not self._batch_mode_active:
                self._try_scale_down()
                await self._try_scale_up()

            if not self._clients:
                raise RuntimeError("No clients available")

            for client in self._clients:
                await ensure_file_ids_for_client(self._parts, client)

            # Keep up to IN_FLIGHT_PER_CLIENT chunks downloading per client and hand them
            # out in order: one client, one request at a time tops out around 9 MB/s;
            # 4 in flight roughly double it (measured 2026-10-25). The client list is read
            # live, so a client given back (scale-down, reclaim, release) gets no new chunks.
            plan = self._chunk_plan(start, end)

            def launch() -> None:
                while self._clients and len(pending) < min(
                    IN_FLIGHT_PER_CLIENT * len(self._clients), MAX_IN_FLIGHT
                ):
                    step = next(plan, None)
                    if step is None:
                        return
                    part, index, skip, take = step
                    pending.append((asyncio.create_task(self._fetch(part, index)), skip, take))

            launch()
            last_rebalance = time.monotonic()
            while pending:
                task, skip, take = pending.popleft()
                data = await task
                if self._force_released:
                    logger.info("[STREAM] Aborting read_range: reader was force-released")
                    return
                # ffmpeg and browsers keep one request open for a whole film: recheck the
                # clients here too, not only when a request starts
                if (
                    not self._batch_mode_active
                    and time.monotonic() - last_rebalance >= REBALANCE_SECONDS
                ):
                    last_rebalance = time.monotonic()
                    self._try_scale_down()
                    await self._try_scale_up()
                launch()
                yield data[skip : skip + take]

        except asyncio.CancelledError:
            raise
        finally:
            for task, _, _ in pending:
                if task.done() and not task.cancelled():
                    task.exception()  # retrieved: no "never retrieved" warning at GC
                else:
                    task.cancel()
            self._active_streams = max(0, self._active_streams - 1)
            if not self._batch_mode_active:
                try:
                    await self._release_workers()
                except Exception:
                    if self._clients:
                        worker_manager.release_clients(self._clients)
                    self._clients = []
