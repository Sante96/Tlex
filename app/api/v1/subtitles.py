"""Subtitle and font extraction API endpoints."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from loguru import logger

from app.api.deps import DBSession
from app.config import get_settings
from app.models.media import CodecType
from app.services.streaming import get_virtual_reader
from app.services.subtitles import subtitle_extractor

settings = get_settings()
router = APIRouter(tags=["subtitles"])

# Subtitle cache directory
SUBTITLE_CACHE_DIR = Path("cache/subtitles")
SUBTITLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Font cache directory
FONT_CACHE_DIR = Path("cache/fonts")
FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Lock to prevent parallel font extraction for same media_id
_font_extraction_locks: dict[int, asyncio.Lock] = {}


@router.get("/{media_id}")
async def get_subtitle(
    media_id: int,
    session: DBSession,
    track: int = Query(0, description="Subtitle track index"),
    format: str = Query("ass", description="Output format: ass or srt"),
) -> Response:
    """
    Extract and return a subtitle track.

    Query params:
    - track: Subtitle track index (default: 0)
    - format: Output format - 'ass' or 'srt' (default: ass)

    Returns:
    - ASS/SRT file content (original, unmodified)
    """
    logger.debug(f"Subtitle request: media={media_id}, track={track}, format={format}")

    if format not in ("ass", "srt"):
        raise HTTPException(status_code=400, detail="Format must be 'ass' or 'srt'")

    # Check cache first (must exist AND have content)
    cache_file = SUBTITLE_CACHE_DIR / f"{media_id}_{track}.{format}"
    if cache_file.exists() and cache_file.stat().st_size > 0:
        logger.debug(f"Serving cached subtitle: {cache_file.name}")
        content = cache_file.read_bytes()
    else:
        # Get subtitle streams to convert absolute index to relative
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.media import MediaItem

        query = select(MediaItem).where(MediaItem.id == media_id).options(selectinload(MediaItem.streams))
        result = await session.execute(query)
        media = result.scalar_one_or_none()

        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        # Find subtitle streams and convert absolute index to relative
        subtitle_streams = sorted(
            [s for s in media.streams if s.codec_type == CodecType.SUBTITLE],
            key=lambda s: s.stream_index
        )

        # Find the relative index for the requested track
        relative_index = None
        for i, s in enumerate(subtitle_streams):
            if s.stream_index == track:
                relative_index = i
                break

        if relative_index is None:
            raise HTTPException(status_code=400, detail=f"Subtitle track {track} not found")

        if relative_index is None:
            raise HTTPException(status_code=400, detail=f"Subtitle track {track} not found")

        logger.debug(f"Extracting subtitle: media={media_id}, track={track}")

        # Use direct MKV extraction (fast - reads only needed bytes)
        try:
            from app.services.subtitles.mkv_extractor import extract_subtitle_direct

            reader = await get_virtual_reader(session, media_id)
            if not reader:
                raise HTTPException(status_code=404, detail="Could not create stream reader")

            content = await extract_subtitle_direct(
                reader,
                track_index=relative_index,
                output_format=format,
            )

            if not content:
                raise HTTPException(status_code=500, detail="Subtitle extraction returned empty content")

            # Cache the result
            cache_file.write_bytes(content)
            logger.debug(f"Cached subtitle: {cache_file.name}")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Subtitle extraction failed: {e}")
            raise HTTPException(status_code=500, detail=str(e) or "Extraction failed") from None

    # Determine content type and filename
    if format == "ass":
        content_type = "text/x-ssa"
        filename = f"subtitle_{media_id}_{track}.ass"
    else:
        content_type = "text/plain"
        filename = f"subtitle_{media_id}_{track}.srt"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/{media_id}/tracks")
async def list_subtitle_tracks(
    media_id: int,
    session: DBSession,
) -> dict:
    """
    List available subtitle tracks for a media item.

    Returns info from database (populated during scan).
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.media import MediaItem

    query = (
        select(MediaItem).where(MediaItem.id == media_id).options(selectinload(MediaItem.streams))
    )
    result = await session.execute(query)
    media = result.scalar_one_or_none()

    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    subtitle_streams = [
        {
            "index": s.stream_index,
            "codec": s.codec_name,
            "language": s.language,
            "title": s.title,
            "is_default": s.is_default,
        }
        for s in media.streams
        if s.codec_type == CodecType.SUBTITLE
    ]

    return {
        "media_id": media_id,
        "tracks": subtitle_streams,
        "count": len(subtitle_streams),
    }


@router.get("/{media_id}/fonts")
async def get_fonts(
    media_id: int,
    session: DBSession,
) -> dict:
    """
    Extract and list all attached fonts from media.

    Returns font metadata. Use /fonts/{media_id}/{filename} to download.
    """
    logger.info(f"GET fonts request: media_id={media_id}")
    # Check cache first (before acquiring lock)
    cache_dir = FONT_CACHE_DIR / str(media_id)
    if cache_dir.exists():
        cached_fonts = list(cache_dir.glob("*"))
        if cached_fonts:
            logger.info(f"Serving {len(cached_fonts)} cached fonts for media {media_id}")
            from app.services.subtitles import extract_font_names

            font_list = []
            for f in cached_fonts:
                font_data = f.read_bytes()
                font_names = extract_font_names(font_data)
                font_list.append({
                    "filename": f.name,
                    "mimetype": "application/x-font-ttf",
                    "size": f.stat().st_size,
                    "url": f"/api/v1/subtitles/{media_id}/font/{f.name}",
                    "names": font_names,
                })

            return {
                "media_id": media_id,
                "fonts": font_list,
                "count": len(cached_fonts),
            }

    # Acquire lock to prevent parallel extraction for same media_id
    if media_id not in _font_extraction_locks:
        _font_extraction_locks[media_id] = asyncio.Lock()

    async with _font_extraction_locks[media_id]:
        # Re-check cache after acquiring lock (another request may have populated it)
        if cache_dir.exists():
            cached_fonts = list(cache_dir.glob("*"))
            if cached_fonts:
                logger.info(f"Serving {len(cached_fonts)} cached fonts for media {media_id} (after lock)")
                from app.services.subtitles import extract_font_names

                font_list = []
                for f in cached_fonts:
                    font_data = f.read_bytes()
                    font_names = extract_font_names(font_data)
                    font_list.append({
                        "filename": f.name,
                        "mimetype": "application/x-font-ttf",
                        "size": f.stat().st_size,
                        "url": f"/api/v1/subtitles/{media_id}/font/{f.name}",
                        "names": font_names,
                    })

                return {
                    "media_id": media_id,
                    "fonts": font_list,
                    "count": len(cached_fonts),
                }

        reader = await get_virtual_reader(session, media_id)
        if reader is None:
            raise HTTPException(status_code=404, detail="Media not found")

        # Use direct reader instead of HTTP self-request for better performance
        try:
            fonts = await subtitle_extractor.extract_all_fonts_from_reader(reader)
        except Exception as e:
            logger.error(f"Font extraction failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

        # Cache extracted fonts
        if fonts:
            cache_dir.mkdir(parents=True, exist_ok=True)
            for f in fonts:
                (cache_dir / f.filename).write_bytes(f.data)
            logger.info(f"Cached {len(fonts)} fonts for media {media_id}")

        return {
            "media_id": media_id,
            "fonts": [
                {
                    "filename": f.filename,
                    "mimetype": f.mimetype,
                    "size": len(f.data),
                    "url": f"/api/v1/subtitles/{media_id}/font/{f.filename}",
                    "names": f.font_names or [],
                }
                for f in fonts
            ],
            "count": len(fonts),
        }


@router.get("/{media_id}/font/{filename}")
async def get_font_file(
    media_id: int,
    filename: str,
    session: DBSession,
) -> Response:
    """
    Download a specific attached font from cache.
    """
    # Check cache first
    cache_file = FONT_CACHE_DIR / str(media_id) / filename
    if cache_file.exists():
        content = cache_file.read_bytes()
        mimetype = "application/x-font-ttf"
        if filename.lower().endswith(".otf"):
            mimetype = "font/otf"
        elif filename.lower().endswith(".woff"):
            mimetype = "font/woff"

        return Response(
            content=content,
            media_type=mimetype,
            headers={
                "Cache-Control": "public, max-age=604800",
                "Access-Control-Allow-Origin": "*",  # CORS for worker
            },
        )

    raise HTTPException(status_code=404, detail=f"Font '{filename}' not found")


@router.post("/{media_id}/warm")
async def warm_subtitle_assets(
    media_id: int,
    session: DBSession,
) -> dict:
    """
    Pre-warm subtitle assets (fonts) in background.

    Called during stream warm to cache fonts before user selects subtitles.
    Returns immediately, extraction happens in background task.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.media import MediaItem

    # Check if fonts are already cached
    cache_dir = FONT_CACHE_DIR / str(media_id)
    if cache_dir.exists() and list(cache_dir.glob("*")):
        logger.debug(f"Font cache exists for media {media_id}, skipping warm")
        return {"status": "cached", "media_id": media_id}

    # Check if media has subtitle streams
    query = select(MediaItem).where(MediaItem.id == media_id).options(selectinload(MediaItem.streams))
    result = await session.execute(query)
    media = result.scalar_one_or_none()

    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    has_subtitles = any(s.codec_type == CodecType.SUBTITLE for s in media.streams)
    if not has_subtitles:
        logger.debug(f"No subtitles in media {media_id}, skipping warm")
        return {"status": "no_subtitles", "media_id": media_id}

    # Start background extraction (don't await)
    async def extract_in_background():
        try:
            async with asyncio.timeout(120):  # 2 min max
                reader = await get_virtual_reader(session, media_id)
                if reader:
                    fonts = await subtitle_extractor.extract_all_fonts_from_reader(reader)
                    if fonts:
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        for f in fonts:
                            (cache_dir / f.filename).write_bytes(f.data)
                        logger.info(f"Background: cached {len(fonts)} fonts for media {media_id}")
        except TimeoutError:
            logger.warning(f"Background font extraction timed out for media {media_id}")
        except Exception as e:
            logger.warning(f"Background font extraction failed for media {media_id}: {e}")

    # Fire and forget
    asyncio.create_task(extract_in_background())

    return {"status": "warming", "media_id": media_id}
