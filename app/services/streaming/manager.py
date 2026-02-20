"""Reader lifecycle management (cache, factory, release, cleanup)."""

import time

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.models.media import MediaItem
from app.services.streaming.reader import VirtualStreamReader

settings = get_settings()

# Readers persist across HTTP range requests so they can accumulate clients
_reader_cache: dict[int, tuple[VirtualStreamReader, float]] = {}
_READER_TTL = 60  # Seconds of inactivity before releasing


async def get_virtual_reader(
    session: AsyncSession, media_id: int, *, persistent: bool = False
) -> VirtualStreamReader | None:
    """
    Get or create a VirtualStreamReader for a media item.

    When persistent=True, the reader is cached and reused across requests.
    This enables dynamic client scaling: each reuse tries to acquire more
    clients from the pool, so the stream gets faster over time.

    Args:
        session: Database session
        media_id: ID of the media item
        persistent: If True, cache the reader for reuse

    Returns:
        VirtualStreamReader or None if media not found
    """
    # Check cache for persistent readers
    if persistent and media_id in _reader_cache:
        reader, _ = _reader_cache[media_id]
        _reader_cache[media_id] = (reader, time.time())
        logger.info(
            f"[READER] Reusing cached reader for media {media_id} "
            f"({len(reader._clients)} clients)"
        )
        return reader

    # Create new reader
    query = (
        select(MediaItem)
        .where(MediaItem.id == media_id)
        .options(selectinload(MediaItem.parts))
    )
    result = await session.execute(query)
    media_item = result.scalar_one_or_none()

    if media_item is None:
        return None

    if not media_item.parts:
        logger.error(f"Media {media_id} has no parts")
        return None

    reader = VirtualStreamReader(
        media_item=media_item,
        session=session,
        chunk_size=settings.chunk_size_bytes,
    )

    if persistent:
        reader._persistent = True
        _reader_cache[media_id] = (reader, time.time())
        logger.info(f"[READER] Created persistent reader for media {media_id}")

    return reader


async def release_reader(media_id: int) -> None:
    """Explicitly release a cached reader and its clients.

    Force-releases immediately regardless of active streams.
    Called when user navigates away — stream is no longer needed.
    """
    entry = _reader_cache.pop(media_id, None)
    if entry:
        reader, _ = entry
        active = reader._active_streams
        reader._persistent = False
        reader._force_released = True
        # Force-release clients back to pool immediately
        if reader._clients:
            count = len(reader._clients)
            worker_manager.release_clients(reader._clients)
            reader._clients = []
            reader._workers = []
            logger.info(
                f"[READER] Force-released {count} client(s) for media {media_id}"
                f"{f' ({active} stream(s) were active)' if active else ''}"
            )


async def cleanup_stale_readers() -> None:
    """Release readers that haven't been used recently and have no active streams."""
    now = time.time()
    stale = [
        mid for mid, (reader, last_access) in _reader_cache.items()
        if now - last_access > _READER_TTL and reader._active_streams == 0
    ]
    for mid in stale:
        await release_reader(mid)
