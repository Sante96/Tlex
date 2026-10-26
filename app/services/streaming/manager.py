"""Reader lifecycle management (cache, factory, release, cleanup)."""

import asyncio
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

# Readers persist across HTTP range requests so they can accumulate clients. One per
# player (viewer: an id the player sends), not per title: two devices on one title
# shared a reader, half the speed each, and one closing its player cut the other
_reader_cache: dict[tuple[int, str], tuple[VirtualStreamReader, float]] = {}
_READER_TTL = 60  # Seconds of inactivity before releasing
# A disconnected request's reader is released this much later, if idle then: ffmpeg drops a
# range request and opens the next one at the same instant, and the next one counts as
# reading only once its body starts (released under it: "reader was force-released")
RELEASE_GRACE = 2.0
_pending_releases: set[asyncio.Task] = set()


def reader_clients(media_id: int, viewer: str = "") -> int:
    """How many clients the player's reader of the title holds now (0: not playing)."""
    entry = _reader_cache.get((media_id, viewer))
    return len(entry[0]._clients) if entry else 0


async def get_virtual_reader(
    session: AsyncSession, media_id: int, *, persistent: bool = False, viewer: str = ""
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
    key = (media_id, viewer)
    # Check cache for persistent readers
    if persistent and key in _reader_cache:
        reader, _ = _reader_cache[key]
        _reader_cache[key] = (reader, time.time())
        logger.info(
            f"[READER] Reusing cached reader for media {media_id} ({len(reader._clients)} clients)"
        )
        return reader

    # Create new reader
    query = select(MediaItem).where(MediaItem.id == media_id).options(selectinload(MediaItem.parts))
    result = await session.execute(query)
    media_item = result.scalar_one_or_none()

    if media_item is None:
        return None

    # Another request may have cached a reader while we awaited the query; reuse it,
    # otherwise the one we'd overwrite keeps its clients forever.
    if persistent and key in _reader_cache:
        return _reader_cache[key][0]

    if not media_item.parts:
        logger.error(f"Media {media_id} has no parts")
        return None

    reader = VirtualStreamReader(media_item=media_item)

    if persistent:
        reader._persistent = True
        _reader_cache[key] = (reader, time.time())
        logger.info(f"[READER] Created persistent reader for media {media_id}")

    return reader


async def release_reader(media_id: int, *, viewer: str = "", only_if_idle: bool = False) -> None:
    """Explicitly release a cached reader and its clients.

    Force-releases immediately regardless of active streams, unless only_if_idle (a
    request ended by a disconnect): then RELEASE_GRACE later, if nothing reads through it
    and nothing took it up since; a reader still serving other requests (ffmpeg's next
    range request, another viewer) is left to them and to cleanup_stale_readers.
    Called when user navigates away — stream is no longer needed.

    NOTE: This function has no internal await points and is therefore safe to
    call from within a CancelledError handler or a finally block.
    """
    if only_if_idle:
        entry = _reader_cache.get((media_id, viewer))
        if entry is not None:
            task = asyncio.create_task(
                _release_if_still_idle(media_id, viewer, entry[0], time.time())
            )
            _pending_releases.add(task)
            task.add_done_callback(_pending_releases.discard)
        return
    entry = _reader_cache.pop((media_id, viewer), None)
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
            logger.info(
                f"[READER] Force-released {count} client(s) for media {media_id}"
                f"{f' ({active} stream(s) were active)' if active else ''}"
            )


async def _release_if_still_idle(
    media_id: int, viewer: str, reader: VirtualStreamReader, since: float
) -> None:
    await asyncio.sleep(RELEASE_GRACE)
    entry = _reader_cache.get((media_id, viewer))
    if entry is None or entry[0] is not reader:
        return
    if reader._active_streams > 0 or entry[1] > since:
        return
    await release_reader(media_id, viewer=viewer)


async def cleanup_stale_readers() -> None:
    """Release readers that haven't been used recently and have no active streams."""
    now = time.time()
    stale = [
        key
        for key, (reader, last_access) in _reader_cache.items()
        if now - last_access > _READER_TTL and reader._active_streams == 0
    ]
    for media_id, viewer in stale:
        await release_reader(media_id, viewer=viewer)
