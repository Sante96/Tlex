"""Subtitle cache: extraction of every track of a media at once, and background warm-up."""

import asyncio
import time
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.media import CodecType, MediaItem
from app.services.streaming import get_virtual_reader
from app.services.subtitles import subtitle_extractor
from app.services.subtitles.builders import build_ass_content, build_srt_content
from app.services.subtitles.mkv_extractor import extract_all_subtitles

# Cache directories
SUBTITLE_CACHE_DIR = Path("cache/subtitles")
FONT_CACHE_DIR = Path("cache/fonts")

# Max concurrent extractions during startup warmup.
# Keep at 1: subtitle extraction reads large byte ranges from Telegram and
# competes directly with active video streams on the same DC connections.
MAX_CONCURRENT = 1

# One extraction per media at a time, shared by player requests and the warm-up. A media
# whose extraction ended without a track (failure, image subtitles) isn't retried for
# RETRY_AFTER seconds, so the player's polling gets a 404 instead of restarting it.
_tasks: dict[int, asyncio.Task] = {}
_finished_at: dict[int, float] = {}
RETRY_AFTER = 60


def subtitle_file(media_id: int, stream_index: int, fmt: str) -> Path:
    return SUBTITLE_CACHE_DIR / f"{media_id}_{stream_index}.{fmt}"


def is_extracting(media_id: int) -> bool:
    return media_id in _tasks


def finished_recently(media_id: int) -> bool:
    return time.monotonic() - _finished_at.get(media_id, float("-inf")) < RETRY_AFTER


def extraction_task(media_id: int, full_read: bool = True) -> asyncio.Task:
    """The media's running subtitle extraction, started if there is none.

    full_read=False (background warm-ups) skips tracks that would need about the whole
    file read; such a run doesn't start the RETRY_AFTER wait, so a request for one of
    those tracks starts a full extraction straight away.
    """
    if media_id not in _tasks:
        _tasks[media_id] = asyncio.create_task(_extract(media_id, full_read))
    return _tasks[media_id]


async def _extract(media_id: int, full_read: bool = True) -> int:
    from app.database import async_session_maker

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(MediaItem)
                .where(MediaItem.id == media_id)
                .options(selectinload(MediaItem.streams))
            )
            media = result.scalar_one_or_none()
            if not media:
                return 0
            indexes = sorted(
                s.stream_index for s in media.streams if s.codec_type == CodecType.SUBTITLE
            )
            reader = await get_virtual_reader(session, media_id)
            if not reader or not indexes:
                return 0
            return await cache_all_subtitle_tracks(reader, media_id, indexes, full_read)
    except Exception as e:
        logger.warning(f"Subtitle extraction failed for media {media_id}: {e}")
        return 0
    finally:
        _tasks.pop(media_id, None)
        if full_read:
            _finished_at[media_id] = time.monotonic()


async def cache_all_subtitle_tracks(
    reader, media_id: int, stream_indexes: list[int], full_read: bool = True
) -> int:
    """Extract every text subtitle track in one pass and cache each as .ass and .srt.

    stream_indexes: the media's subtitle stream indexes in order (the MKV lists its
    subtitle tracks in the same order). Returns how many tracks were cached.
    """
    started = time.monotonic()
    extracted = await extract_all_subtitles(reader, full_read)
    if not extracted:
        return 0

    SUBTITLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = 0
    for stream_index, (track, events) in zip(stream_indexes, extracted, strict=False):
        if events is None:  # image subtitles
            continue
        subtitle_file(media_id, stream_index, "ass").write_bytes(build_ass_content(track, events))
        # An empty file reads as "not cached": keep a track without lines servable
        subtitle_file(media_id, stream_index, "srt").write_bytes(build_srt_content(events) or b"\n")
        cached += 1
    logger.info(
        f"Cached {cached} subtitle tracks for media {media_id} in {time.monotonic() - started:.1f}s"
    )
    return cached


async def pre_extract_fonts(media_id: int, session: AsyncSession) -> bool:
    """
    Extract and cache fonts for a media item.

    Returns True if fonts were extracted, False if already cached or no fonts.
    """
    cache_dir = FONT_CACHE_DIR / str(media_id)

    # Skip if already checked (dir exists = already processed, even if empty = no fonts)
    if cache_dir.exists():
        return False

    try:
        reader = await get_virtual_reader(session, media_id)
        if not reader:
            return False

        fonts = await subtitle_extractor.extract_all_fonts_from_reader(reader)

        # Always create the directory as a marker that we checked
        cache_dir.mkdir(parents=True, exist_ok=True)

        if fonts:
            for f in fonts:
                (cache_dir / f.filename).write_bytes(f.data)
            logger.info(f"Cached {len(fonts)} fonts for media {media_id}")
            return True
        else:
            logger.debug(f"No fonts found for media {media_id}, marked as checked")

    except Exception as e:
        logger.warning(f"Failed to extract fonts for media {media_id}: {e}")

    return False


async def pre_extract_subtitles(media_id: int, session: AsyncSession) -> int:
    """Extract and cache every subtitle track of a media item, unless that was done already.

    Returns the number of tracks cached.
    """
    result = await session.execute(
        select(MediaItem).where(MediaItem.id == media_id).options(selectinload(MediaItem.streams))
    )
    media = result.scalar_one_or_none()
    if not media:
        return 0

    indexes = [s.stream_index for s in media.streams if s.codec_type == CodecType.SUBTITLE]
    # Every text track is cached in the same pass: one on disk means the media is done
    if not indexes or any(subtitle_file(media_id, i, "ass").exists() for i in indexes):
        return 0
    # shield: our caller giving up mustn't cancel an extraction the player may be waiting on
    return await asyncio.shield(extraction_task(media_id, full_read=False))


async def ensure_cache_populated(media_id: int, session: AsyncSession) -> None:
    """Check cache and extract missing fonts/subtitles for a media item."""
    await pre_extract_fonts(media_id, session)
    await pre_extract_subtitles(media_id, session)


async def populate_all_caches(session: AsyncSession) -> None:
    """
    Startup task: populate caches for all media with subtitles.

    Runs in background with concurrency limit to avoid overloading.
    """
    # Find all media with subtitle streams
    query = select(MediaItem).options(selectinload(MediaItem.streams))
    result = await session.execute(query)
    all_media = result.scalars().all()

    # Filter to media with subtitles that need cache population
    media_needing_cache = []

    for media in all_media:
        has_subtitles = any(s.codec_type == CodecType.SUBTITLE for s in media.streams)
        if not has_subtitles:
            continue

        # Check if fonts were already checked (dir exists = already processed)
        font_cache = FONT_CACHE_DIR / str(media.id)
        fonts_cached = font_cache.exists()

        # Check if any subtitle is cached
        subtitle_cached = any(
            (SUBTITLE_CACHE_DIR / f"{media.id}_{s.stream_index}.ass").exists()
            for s in media.streams
            if s.codec_type == CodecType.SUBTITLE
        )

        if not fonts_cached or not subtitle_cached:
            media_needing_cache.append(media.id)

    if not media_needing_cache:
        logger.info("All subtitle caches are populated")
        return

    logger.info(f"Starting subtitle cache population for {len(media_needing_cache)} media items")

    # Use semaphore to limit concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def extract_with_limit(media_id: int):
        async with semaphore:
            try:
                # Create new session for this extraction
                from app.database import async_session_maker

                async with async_session_maker() as extract_session:
                    await ensure_cache_populated(media_id, extract_session)
            except Exception as e:
                logger.warning(f"Cache population failed for media {media_id}: {e}")

    # Start all extractions (limited by semaphore)
    tasks = [extract_with_limit(mid) for mid in media_needing_cache]
    await asyncio.gather(*tasks)

    logger.info("Background cache population complete")
