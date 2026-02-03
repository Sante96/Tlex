"""Virtual Stream Reader implementation."""

import asyncio
import time
from collections.abc import AsyncIterator

from loguru import logger
from pyrogram import Client
from pyrogram.errors import FileReferenceExpired, FloodWait
from sqlalchemy import select, update
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
        self._worker = None
        self._client: Client | None = None

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

    async def _ensure_worker(self) -> bool:
        """Ensure we have a worker client available."""
        if self._client is not None:
            return True

        result = await worker_manager.get_best_worker(self._session)
        if result is None:
            logger.error("No workers available for streaming")
            return False

        self._worker, self._client = result
        return True

    async def _release_worker(self) -> None:
        """Release the worker when done streaming."""
        self._worker = None
        self._client = None

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

        if not await self._ensure_worker():
            raise RuntimeError("No workers available")

        # Pre-refresh all file_ids to avoid FileReferenceExpired during streaming
        await self._refresh_all_file_ids()

        current_offset = start
        bytes_remaining = end - start

        try:
            while bytes_remaining > 0:
                position = self._find_part_for_offset(current_offset)
                if position is None:
                    break

                part = position.part
                local_offset = position.local_offset

                # Calculate how many bytes to read from this part
                bytes_in_part = part.file_size - local_offset
                bytes_to_read = min(bytes_remaining, bytes_in_part)

                async for chunk in self._stream_part(part, local_offset, bytes_to_read):
                    yield chunk
                    chunk_len = len(chunk)
                    current_offset += chunk_len
                    bytes_remaining -= chunk_len

        finally:
            await self._release_worker()

    async def _populate_peer_cache(self) -> None:
        """Populate Pyrogram peer cache by iterating dialogs."""
        if self._client is None:
            return

        channel_ids = {p.channel_id for p in self._parts}
        for channel_id in channel_ids:
            try:
                async for dialog in self._client.get_dialogs():
                    if dialog.chat and dialog.chat.id == channel_id:
                        logger.debug(f"Found channel {channel_id} in dialogs cache")
                        break
            except Exception as e:
                logger.warning(f"Failed to populate peer cache: {e}")

    async def _refresh_file_id(self, part: MediaPart, commit: bool = True) -> str | None:
        """
        Refresh expired file_id by fetching the original message.

        Args:
            part: The MediaPart with expired file_id
            commit: Whether to commit the session after update

        Returns:
            New file_id or None if refresh failed
        """
        if self._client is None:
            return None

        try:
            logger.debug(f"Refreshing file_id for part {part.part_index}")

            messages = await self._client.get_messages(
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

            stmt = (
                update(MediaPart)
                .where(MediaPart.id == part.id)
                .values(telegram_file_id=new_file_id)
            )
            await self._session.execute(stmt)

            if commit:
                await self._session.commit()

            part.telegram_file_id = new_file_id
            _FILE_ID_CACHE[part.id] = (new_file_id, time.time())
            logger.debug(f"Refreshed file_id for part {part.part_index}")
            return new_file_id

        except Exception as e:
            logger.error(f"Failed to refresh file_id for part {part.part_index}: {e}")
            return None

    async def _refresh_all_file_ids(self) -> None:
        """Pre-refresh all file_ids to prevent FileReferenceExpired during streaming."""
        if not await self._ensure_worker():
            logger.warning("No worker available for file_id refresh")
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
            await self._refresh_file_id(part, commit=False)

        await self._session.commit()

    async def _stream_part(self, part: MediaPart, offset: int, length: int) -> AsyncIterator[bytes]:
        """
        Stream bytes from a single part with retry logic.

        Uses Pyrogram's `stream_media` with offset/limit calculated in chunks (1MB).
        It handles:
        - Calculation of chunk offsets and alignment.
        - Skipping initial bytes if offset is not chunk-aligned.
        - Retry logic for expired file references and flood waits.

        Args:
            part: The MediaPart to stream from.
            offset: Local byte offset within the part.
            length: Number of bytes to read.

        Yields:
            Chunks of bytes.
        """
        if self._client is None:
            raise RuntimeError("No client available")

        max_retries = 5
        bytes_read = 0
        file_id = part.telegram_file_id

        chunk_offset = offset // PYROGRAM_CHUNK_SIZE
        skip_bytes = offset % PYROGRAM_CHUNK_SIZE  # Bytes to skip in first chunk

        # Calculate how many chunks we need
        chunks_needed = (length + skip_bytes + PYROGRAM_CHUNK_SIZE - 1) // PYROGRAM_CHUNK_SIZE

        logger.debug(
            f"Streaming part {part.part_index}: offset={offset}, len={length}, chunks={chunks_needed}"
        )

        # Check cache for already downloaded chunks
        cache_hits = 0
        for idx in range(chunk_offset, chunk_offset + chunks_needed):
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
                if bytes_read + chunk_len > length:
                    needed = length - bytes_read
                    yield chunk[:needed]
                    bytes_read += needed
                else:
                    yield chunk
                    bytes_read += chunk_len

                if bytes_read >= length:
                    if cache_hits > 0:
                        logger.debug(f"Served {cache_hits} chunks from cache")
                    return
            else:
                break

        if bytes_read >= length:
            if cache_hits > 0:
                logger.debug(f"Served {cache_hits} chunks from cache (complete)")
            return

        remaining_offset = chunk_offset + cache_hits
        remaining_chunks = chunks_needed - cache_hits

        if cache_hits > 0:
            logger.debug(f"Cache hit: {cache_hits} chunks, fetching {remaining_chunks} more")

        current_chunk_idx = remaining_offset
        for attempt in range(max_retries):
            try:
                async for chunk in self._client.stream_media(
                    file_id,
                    offset=remaining_offset,
                    limit=remaining_chunks,
                ):
                    _cache_chunk(part.id, current_chunk_idx, chunk)
                    current_chunk_idx += 1

                    if skip_bytes > 0:
                        if len(chunk) <= skip_bytes:
                            skip_bytes -= len(chunk)
                            continue
                        chunk = chunk[skip_bytes:]
                        skip_bytes = 0

                    if not chunk:
                        continue

                    chunk_len = len(chunk)
                    if bytes_read + chunk_len > length:
                        needed = length - bytes_read
                        yield chunk[:needed]
                        bytes_read += needed
                        return
                    else:
                        yield chunk
                        bytes_read += chunk_len

                    if bytes_read >= length:
                        return

                return

            except FileReferenceExpired as e:
                logger.warning(f"FileReferenceExpired for part {part.id}: {e}")
                new_file_id = await self._refresh_file_id(part)
                if new_file_id:
                    file_id = new_file_id
                    logger.debug(f"Retrying with new file_id for part {part.id}")
                    continue
                else:
                    raise RuntimeError("Failed to refresh expired file reference") from None

            except FloodWait as e:
                logger.warning(f"FloodWait {e.value}s, waiting...")
                await asyncio.sleep(e.value)

            except AttributeError as e:
                # BadMsgNotification causes "'BadMsgNotification' object has no attribute 'bytes'"
                # This happens when MTProto session is desync'd - retry usually works
                if "BadMsgNotification" in str(e) or "bytes" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = 0.5 * (attempt + 1)
                        logger.warning(
                            f"Session desync on part {part.id}, retry {attempt + 1}/{max_retries} in {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries for session desync on part {part.id}")
                        raise
                else:
                    raise

            except TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Timeout on part {part.id}, retry {attempt + 1}/{max_retries} in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max retries reached for part {part.id}")
                    raise

            except Exception as e:
                logger.error(f"Error streaming part {part.id}: {e}")
                raise


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
