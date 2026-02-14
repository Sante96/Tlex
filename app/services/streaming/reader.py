"""Virtual Stream Reader implementation."""

import asyncio
import time
from collections.abc import AsyncIterator

from loguru import logger
from pyrogram import Client
from pyrogram.errors import FileReferenceExpired, FloodWait, RPCError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.models.media import MediaItem, MediaPart
from app.services.streaming.cache import (
    _FILE_ID_CACHE,
    _FILE_ID_CACHE_TTL,
    PYROGRAM_CHUNK_SIZE,
    _cache_chunk,
    _get_cached_chunk,
    invalidate_file_id_cache,
)
from app.services.streaming.models import StreamPosition

settings = get_settings()


class VirtualStreamReader:
    """
    Reads bytes from a virtual file composed of multiple Telegram parts.

    This class provides a unified file-like interface over multiple split parts
    stored on Telegram. It handles:
    - Transparent concatenation of split files.
    - Seeking to any byte offset (supporting Range requests).
    - Seamless boundary crossing between parts.
    - Chunked streaming for memory efficiency.
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
        self._current_position = 0
        self._workers: list = []
        self._clients: list[Client] = []
        self._batch_mode_active = False
        self._rr_counter = 0  # Round-robin counter

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

    def _find_part_for_offset(self, byte_offset: int) -> StreamPosition | None:
        """
        Find which part contains the given byte offset.

        Returns:
            StreamPosition with the part and local offset, or None if out of bounds.
        """
        if byte_offset < 0 or byte_offset >= self._total_size:
            return None

        for part in self._parts:
            if part.contains_byte(byte_offset):
                return StreamPosition(
                    part=part,
                    local_offset=part.local_offset(byte_offset),
                )

        return None

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def batch_mode(self):
        """
        Context manager for batch operations (e.g. subtitle extraction).

        Acquires workers and refreshes file IDs ONCE, then allows multiple
        read_range calls without repeated overhead.
        """
        if self._batch_mode_active:
            yield
            return

        if not await self._ensure_workers():
            raise RuntimeError("No workers available")

        # Refresh all IDs once using the first client
        await self._refresh_all_file_ids()

        self._batch_mode_active = True
        try:
            yield
        finally:
            self._batch_mode_active = False
            await self._release_workers()

    async def _ensure_workers(self) -> bool:
        """Ensure we have worker clients available (pool)."""
        if self._clients:
            return True

        # Use 3 clients for striping (parallel download from multiple workers)
        clients = await worker_manager.get_available_clients(limit=3)
        if not clients:
            logger.error("No workers available for streaming")
            return False

        self._clients = clients
        self._workers = []  # Not needed anymore

        logger.debug(f"Using {len(self._clients)} workers for striping")
        return True

    async def _release_workers(self) -> None:
        """Release workers back to the pool for reuse."""
        if self._batch_mode_active:
            return

        # Release clients back to the pool so other requests can use them
        if self._clients:
            worker_manager.release_clients(self._clients)

        self._workers = []
        self._clients = []

    async def read_range(self, start: int, end: int | None = None) -> AsyncIterator[bytes]:
        """
        Read a range of bytes from the virtual stream.

        This generator yields chunks of bytes corresponding to the requested range,
        automatically handling part boundaries and fetching data from Telegram.

        Args:
            start: Start byte offset (inclusive).
            end: End byte offset (exclusive). If None, reads until the end of the file.

        Yields:
            Chunks of bytes from the requested range.

        Raises:
            RuntimeError: If no worker clients are available.
        """
        if end is None:
            end = self._total_size

        # Clamp to valid range
        start = max(0, start)
        end = min(end, self._total_size)

        if start >= end:
            return

        try:
            if not self._batch_mode_active:
                if not await self._ensure_workers():
                    raise RuntimeError("No workers available")

                # Pre-refresh all file_ids to avoid FileReferenceExpired during streaming
                await self._refresh_all_file_ids()

            # Select worker for this range request (Round-Robin)
            if not self._clients:
                raise RuntimeError("No clients available")

            client_idx = self._rr_counter % len(self._clients)
            self._rr_counter += 1
            client = self._clients[client_idx]

            # Proactively refresh file_ids for THIS client before streaming
            # file_reference is session-specific, so each client needs its own
            await self._ensure_file_ids_for_client(client)

            current_offset = start
            bytes_read = 0

            while current_offset < end:
                # Find which part contains the current offset
                pos = self._find_part_for_offset(current_offset)
                if not pos:
                    break

                # Calculate how many bytes to read from this part
                part_remaining_bytes = pos.part.file_size - pos.local_offset
                # Don't read past the global end
                chunk_len = min(part_remaining_bytes, end - current_offset)

                # Stream from this part using the selected client
                async for chunk in self._stream_part(
                    client,
                    pos.part,
                    offset=pos.local_offset,
                    length=chunk_len,
                ):
                    yield chunk
                    chunk_size = len(chunk)
                    current_offset += chunk_size
                    bytes_read += chunk_size

                    # Verify we didn't overshoot
                    if current_offset >= end:
                        break

                # If connection dropped or part ended, loop will continue to next part
                # or break if done

        except asyncio.CancelledError:
            raise
        finally:
            if not self._batch_mode_active:
                try:
                    await self._release_workers()
                except Exception:
                    # Ensure workers are released even if cleanup fails
                    if self._clients:
                        worker_manager.release_clients(self._clients)
                    self._workers = []
                    self._clients = []

    async def _populate_peer_cache(self) -> None:
        """Populate Pyrogram peer cache (using first client)."""
        if not self._clients:
            return

        client = self._clients[0]
        channel_ids = {p.channel_id for p in self._parts}

        for channel_id in channel_ids:
            logger.debug(f"Ensuring peer knowledge for channel {channel_id}")
            try:
                # Fast path: direct lookup (fetches if needed, uses cache if available)
                await client.get_chat(channel_id)
                continue
            except Exception as e:
                logger.debug(f"get_chat({channel_id}) failed: {e}. Falling back to dialogs scan.")

            # Slow path: iterate dialogs
            try:
                found = False
                async for dialog in client.get_dialogs():
                    if dialog.chat and dialog.chat.id == channel_id:
                        logger.debug(f"Found channel {channel_id} in dialogs cache")
                        found = True
                        break
                if not found:
                    logger.warning(f"Channel {channel_id} not found in dialogs")
            except Exception as e:
                logger.warning(f"Failed to populate peer cache via dialogs: {e}")

    async def _refresh_file_id(
        self, part: MediaPart, commit: bool = False, client: Client | None = None
    ) -> str | None:
        """
        Refresh expired file_id by fetching the original message.

        NOTE: Does NOT update DB to avoid race conditions during parallel streaming.
        The file_id is only cached in memory. DB will be updated during next scan.

        Args:
            part: The media part to refresh
            commit: Ignored (kept for API compatibility)
            client: Specific client to use (important: file_reference is session-specific!)
        """
        if client is None:
            if not self._clients:
                return None
            client = self._clients[0]

        try:
            logger.debug(f"Refreshing file_id for part {part.part_index}")

            messages = await client.get_messages(
                chat_id=part.channel_id,
                message_ids=part.message_id,
            )

            if not messages:
                logger.error(f"Message {part.message_id} not found")
                return None

            message = messages if not isinstance(messages, list) else messages[0]
            doc = message.document or message.video

            if not doc:
                logger.error(f"No document in message {part.message_id}")
                return None

            new_file_id = doc.file_id

            # Only update in-memory, no DB operations to avoid race conditions
            part.telegram_file_id = new_file_id
            logger.debug(f"Refreshed file_id for part {part.part_index}")
            return new_file_id

        except Exception as e:
            logger.error(f"Failed to refresh file_id for part {part.part_index}: {e}")
            return None

    async def _refresh_all_file_ids(self) -> None:
        """
        Pre-refresh all file_ids to prevent FileReferenceExpired during streaming.

        NOTE: With multiple workers, this only refreshes for client[0].
        Other clients will refresh on-demand in _stream_part when they encounter
        FileReferenceExpired, since file_reference is session-specific.
        """
        if not await self._ensure_workers():
            logger.warning("No workers available for file_id refresh")
            return

        now = time.time()
        needs_refresh = False

        # Check if any part needs refresh
        for part in self._parts:
            cached = _FILE_ID_CACHE.get(part.id)
            if cached is None:
                logger.debug(f"Part {part.id} not in cache, needs refresh")
                needs_refresh = True
                break
            elif (now - cached[1]) > _FILE_ID_CACHE_TTL:
                logger.debug(f"Part {part.id} cache expired (age={(now - cached[1]):.0f}s), needs refresh")
                needs_refresh = True
                break
            else:
                part.telegram_file_id = cached[0]

        if not needs_refresh:
            logger.debug("All file_ids are cached, skipping refresh")
            return

        await self._populate_peer_cache()

        for part in self._parts:
            cached = _FILE_ID_CACHE.get(part.id)
            if cached and (now - cached[1]) <= _FILE_ID_CACHE_TTL:
                part.telegram_file_id = cached[0]
                continue
            await self._refresh_file_id(part)

    async def _ensure_file_ids_for_client(self, client: Client) -> None:
        """
        Ensure all parts have valid file_ids for the specified client.

        Since file_reference is session-specific in Telegram, each client needs
        its own refresh. This is called proactively before streaming to avoid
        FileReferenceExpired errors during the stream.
        """
        # Use client-specific cache key
        client_id = id(client)

        for part in self._parts:
            cache_key = (part.id, client_id)

            # Check if we have a recent file_id for this client+part combo
            cached = _FILE_ID_CACHE.get(cache_key)
            now = time.time()

            if cached and (now - cached[1]) <= _FILE_ID_CACHE_TTL:
                # Use cached file_id
                part.telegram_file_id = cached[0]
                continue

            # Need to refresh for this client
            logger.debug(f"Refreshing file_id for part {part.part_index} (client {client_id})")
            new_file_id = await self._refresh_file_id(part, client=client)
            if new_file_id:
                # Cache with client-specific key
                _FILE_ID_CACHE[cache_key] = (new_file_id, now)

    async def _stream_part(self, client: Client, part: MediaPart, offset: int, length: int) -> AsyncIterator[bytes]:
        """
        Stream bytes from a single part with retry logic.

        Handles FileReferenceExpired by refreshing file_id and resuming from
        the last successfully downloaded chunk position.
        """
        if not client:
            raise RuntimeError("No client provided")

        max_retries = 5
        bytes_yielded = 0
        file_id = part.telegram_file_id

        initial_chunk_offset = offset // PYROGRAM_CHUNK_SIZE
        initial_skip_bytes = offset % PYROGRAM_CHUNK_SIZE

        # Calculate total chunks needed
        total_chunks_needed = (length + initial_skip_bytes + PYROGRAM_CHUNK_SIZE - 1) // PYROGRAM_CHUNK_SIZE

        logger.debug(
            f"Streaming part {part.part_index}: offset={offset}, len={length}, chunks={total_chunks_needed}"
        )

        # Phase 1: Serve from cache
        cache_hits = 0
        skip_bytes = initial_skip_bytes
        for idx in range(initial_chunk_offset, initial_chunk_offset + total_chunks_needed):
            cached = _get_cached_chunk(part.id, idx)
            if cached:
                cache_hits += 1
                chunk = cached

                if skip_bytes > 0:
                    if len(chunk) <= skip_bytes:
                        skip_bytes -= len(chunk)
                        continue
                    chunk = chunk[skip_bytes:]
                    skip_bytes = 0

                if not chunk:
                    continue

                chunk_len = len(chunk)
                if bytes_yielded + chunk_len > length:
                    needed = length - bytes_yielded
                    yield chunk[:needed]
                    bytes_yielded += needed
                else:
                    yield chunk
                    bytes_yielded += chunk_len

                if bytes_yielded >= length:
                    if cache_hits > 0:
                        logger.debug(f"Served {cache_hits} chunks from cache")
                    return
            else:
                break

        if bytes_yielded >= length:
            if cache_hits > 0:
                logger.debug(f"Served {cache_hits} chunks from cache (complete)")
            return

        # Phase 2: Fetch remaining chunks from Telegram with retry
        # Track position for resume after errors
        next_chunk_to_fetch = initial_chunk_offset + cache_hits
        chunks_remaining = total_chunks_needed - cache_hits
        skip_bytes_for_fetch = initial_skip_bytes if cache_hits == 0 else 0

        if cache_hits > 0:
            logger.debug(f"Cache hit: {cache_hits} chunks, fetching {chunks_remaining} more")

        # Use while loop so refresh doesn't consume an attempt
        attempt = 0
        consecutive_failures = 0
        max_consecutive_failures = 3

        while attempt < max_retries:
            try:
                chunks_fetched_this_attempt = 0
                async for chunk in client.stream_media(
                    file_id,
                    offset=next_chunk_to_fetch,
                    limit=chunks_remaining,
                ):
                    # Cache the chunk
                    _cache_chunk(part.id, next_chunk_to_fetch, chunk)
                    chunks_fetched_this_attempt += 1

                    # Update position for potential resume
                    next_chunk_to_fetch += 1
                    chunks_remaining -= 1

                    # Handle skip bytes for first chunk
                    if skip_bytes_for_fetch > 0:
                        if len(chunk) <= skip_bytes_for_fetch:
                            skip_bytes_for_fetch -= len(chunk)
                            continue
                        chunk = chunk[skip_bytes_for_fetch:]
                        skip_bytes_for_fetch = 0

                    if not chunk:
                        continue

                    chunk_len = len(chunk)
                    if bytes_yielded + chunk_len > length:
                        needed = length - bytes_yielded
                        yield chunk[:needed]
                        bytes_yielded += needed
                        return
                    else:
                        yield chunk
                        bytes_yielded += chunk_len

                    if bytes_yielded >= length:
                        return

                # Check if we got all expected chunks
                if chunks_remaining > 0:
                    consecutive_failures += 1
                    wait_time = 1.0 * consecutive_failures
                    logger.warning(
                        f"[INCOMPLETE] Stream ended early for part {part.id}: "
                        f"got {chunks_fetched_this_attempt} chunks this attempt, "
                        f"{chunks_remaining} remaining (failure {consecutive_failures}/{max_consecutive_failures})"
                    )

                    if consecutive_failures >= max_consecutive_failures:
                        # Too many consecutive failures with 0 chunks - refresh file_id
                        logger.warning(
                            f"[REFRESH] {consecutive_failures} consecutive failures, "
                            f"refreshing file_id for part {part.id}"
                        )
                        await asyncio.sleep(wait_time)
                        invalidate_file_id_cache(part.id, client_id=id(client))
                        new_file_id = await self._refresh_file_id(part, client=client)
                        if new_file_id:
                            file_id = new_file_id
                            consecutive_failures = 0  # Reset after successful refresh
                            logger.info(f"[REFRESH] Got new file_id for part {part.id}, retrying")
                            attempt += 1  # Count as attempt only after refresh
                            continue
                        else:
                            logger.error("Failed to refresh file_id")
                            raise RuntimeError("Failed to refresh expired file reference")
                    else:
                        # Wait and retry without refresh
                        await asyncio.sleep(wait_time)
                        continue

                # Successfully completed
                return

            except RPCError as e:
                logger.warning(f"[RETRY] Caught RPCError at chunk {next_chunk_to_fetch}: {type(e).__name__}")
                attempt += 1

                is_expired = isinstance(e, FileReferenceExpired)
                if not is_expired:
                    err_str = str(e)
                    err_id = getattr(e, "ID", "")
                    if "FILE_REFERENCE" in err_id or "FILE_REFERENCE" in err_str:
                        is_expired = True

                if is_expired:
                    logger.warning(
                        f"FileReferenceExpired for part {part.id}, attempt {attempt}/{max_retries}"
                    )
                    invalidate_file_id_cache(part.id, client_id=id(client))
                    new_file_id = await self._refresh_file_id(part, client=client)
                    if new_file_id:
                        file_id = new_file_id
                        logger.info(f"Refreshed file_id, resuming from chunk {next_chunk_to_fetch}")
                        continue
                    else:
                        raise RuntimeError("Failed to refresh expired file reference") from e

                if isinstance(e, FloodWait):
                    logger.warning(f"FloodWait {e.value}s, waiting...")
                    await asyncio.sleep(e.value)
                    continue

                raise

            except AttributeError as e:
                if "BadMsgNotification" in str(e) or "bytes" in str(e):
                    attempt += 1
                    if attempt < max_retries:
                        wait_time = 0.5 * attempt
                        logger.warning(f"Session desync, retry {attempt}/{max_retries} in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise
                else:
                    raise

            except TimeoutError:
                attempt += 1
                if attempt < max_retries:
                    wait_time = attempt * 2
                    logger.warning(f"Timeout, retry {attempt}/{max_retries} in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise

            except Exception as e:
                logger.error(f"Unexpected error streaming part {part.id}: {type(e).__name__}: {e}")
                raise

        logger.error(f"Exhausted all {max_retries} retries for part {part.id}")
        raise RuntimeError(f"Failed to stream part {part.id} after {max_retries} retries")


async def get_virtual_reader(session: AsyncSession, media_id: int) -> VirtualStreamReader | None:
    """
    Factory function to create a VirtualStreamReader for a media item.

    Args:
        session: Database session
        media_id: ID of the media item

    Returns:
        VirtualStreamReader or None if media not found
    """
    query = select(MediaItem).where(MediaItem.id == media_id).options(selectinload(MediaItem.parts))
    result = await session.execute(query)
    media_item = result.scalar_one_or_none()

    if media_item is None:
        return None

    if not media_item.parts:
        logger.error(f"Media {media_id} has no parts")
        return None

    return VirtualStreamReader(
        media_item=media_item,
        session=session,
        chunk_size=settings.chunk_size_bytes,
    )
