"""Virtual Stream Reader — unified file-like interface over Telegram parts."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from loguru import logger
from pyrogram import Client
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.worker_manager import MAX_CLIENTS_PER_STREAM, worker_manager
from app.models.media import MediaItem, MediaPart
from app.services.streaming.download import stream_part
from app.services.streaming.models import StreamPosition
from app.services.streaming.telegram import (
    ensure_file_ids_for_client,
    refresh_all_file_ids,
)


class VirtualStreamReader:
    """
    Reads bytes from a virtual file composed of multiple Telegram parts.

    Handles transparent concatenation of split files, seeking to any byte
    offset, seamless boundary crossing, and chunked streaming.
    """

    def __init__(
        self,
        media_item: MediaItem,
        session: AsyncSession,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        self._media_item = media_item
        self._session = session
        self._chunk_size = chunk_size
        self._parts: list[MediaPart] = sorted(media_item.parts, key=lambda p: p.part_index)
        self._total_size = sum(p.file_size for p in self._parts)
        self._current_position = 0
        self._workers: list = []
        self._clients: list[Client] = []
        self._batch_mode_active = False
        self._persistent = False
        self._rr_counter = 0
        self._active_streams = 0
        self._force_released = False

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
        if not clients:
            logger.error("No workers available for streaming")
            return False
        self._clients = clients
        self._workers = []
        logger.info(f"[STREAM] Acquired {len(self._clients)} client(s) from pool")
        return True

    async def _try_scale_up(self) -> None:
        """Try to dynamically acquire one more client from the pool."""
        if len(self._clients) >= MAX_CLIENTS_PER_STREAM:
            return
        if worker_manager.pool_pressure() > 0.75:
            return

        client = await worker_manager.try_acquire_one()
        if client is None:
            return
        if len(self._clients) >= MAX_CLIENTS_PER_STREAM:
            worker_manager.release_clients([client])
            return

        try:
            await ensure_file_ids_for_client(self._parts, client)
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
        if pressure <= 0.75:
            return
        released = self._clients.pop()
        worker_manager.release_clients([released])
        logger.info(
            f"[STREAM] Scale-down: now {len(self._clients)} clients "
            f"(pool pressure {pressure:.0%})"
        )

    async def _release_workers(self) -> None:
        """Release workers back to the pool for reuse."""
        if self._batch_mode_active or self._persistent:
            return
        if self._clients:
            count = len(self._clients)
            worker_manager.release_clients(self._clients)
            logger.info(f"[STREAM] Released {count} client(s) back to pool")
        self._workers = []
        self._clients = []

    # --- Main streaming ---

    async def read_range(self, start: int, end: int | None = None) -> AsyncIterator[bytes]:
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

            client_idx = self._rr_counter % len(self._clients)
            self._rr_counter += 1
            client = self._clients[client_idx]

            await ensure_file_ids_for_client(self._parts, client)

            current_offset = start

            while current_offset < end:
                if self._force_released:
                    logger.info("[STREAM] Aborting read_range: reader was force-released")
                    return

                pos = self._find_part_for_offset(current_offset)
                if not pos:
                    break

                part_remaining = pos.part.file_size - pos.local_offset
                chunk_len = min(part_remaining, end - current_offset)

                async for chunk in stream_part(
                    client,
                    pos.part,
                    offset=pos.local_offset,
                    length=chunk_len,
                    is_force_released=lambda: self._force_released,
                ):
                    yield chunk
                    current_offset += len(chunk)
                    if current_offset >= end:
                        break

        except asyncio.CancelledError:
            raise
        finally:
            self._active_streams = max(0, self._active_streams - 1)
            if not self._batch_mode_active:
                try:
                    await self._release_workers()
                except Exception:
                    if self._clients:
                        worker_manager.release_clients(self._clients)
                    self._workers = []
                    self._clients = []
