"""Subtitle cache service for background pre-extraction."""

import asyncio
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.media import CodecType, MediaItem
from app.services.streaming import get_virtual_reader
from app.services.subtitles import subtitle_extractor

# Cache directories
SUBTITLE_CACHE_DIR = Path("cache/subtitles")
FONT_CACHE_DIR = Path("cache/fonts")

# Max concurrent extractions to avoid overloading Telegram
MAX_CONCURRENT = 1


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
    """
    Extract and cache the FIRST subtitle track for a media item.

    Uses direct MKV extraction first (fast), falls back to FFmpeg if needed.

    Returns number of subtitles extracted (0 or 1).
    """
    # Get media with streams
    query = (
        select(MediaItem)
        .where(MediaItem.id == media_id)
        .options(selectinload(MediaItem.streams))
    )
    result = await session.execute(query)
    media = result.scalar_one_or_none()

    if not media:
        return 0

    # Find subtitle streams, sorted by index
    subtitle_streams = sorted(
        [s for s in media.streams if s.codec_type == CodecType.SUBTITLE],
        key=lambda s: s.stream_index
    )

    if not subtitle_streams:
        return 0

    # Only extract the first subtitle track
    first_stream = subtitle_streams[0]

    # Check if already cached
    cache_ass = SUBTITLE_CACHE_DIR / f"{media_id}_{first_stream.stream_index}.ass"
    cache_srt = SUBTITLE_CACHE_DIR / f"{media_id}_{first_stream.stream_index}.srt"

    if (cache_ass.exists() and cache_ass.stat().st_size > 0) or \
       (cache_srt.exists() and cache_srt.stat().st_size > 0):
        return 0

    content = None

    # Direct MKV extraction (fast - reads only needed bytes)
    try:
        from app.services.subtitles.mkv_extractor import extract_subtitle_direct

        reader = await get_virtual_reader(session, media_id)
        if reader:
            content = await extract_subtitle_direct(
                reader,
                track_index=0,
                output_format="ass",
            )
            if content:
                logger.info(f"Subtitle extraction succeeded for media {media_id}")
    except Exception as e:
        logger.warning(f"Subtitle extraction failed for media {media_id}: {e}")

    if content:
        SUBTITLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_ass.write_bytes(content)
        logger.info(f"Cached first subtitle for media {media_id}")
        return 1

    return 0


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
    query = (
        select(MediaItem)
        .options(selectinload(MediaItem.streams))
    )
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
            for s in media.streams if s.codec_type == CodecType.SUBTITLE
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
