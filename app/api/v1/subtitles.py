"""Subtitle and font extraction API endpoints."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from loguru import logger

from app.api.deps import DBSession
from app.config import get_settings
from app.models.media import CodecType
from app.services.streaming import get_virtual_reader
from app.services.subtitles import subtitle_extractor
from app.services.subtitles.cache import (
    extraction_task,
    finished_recently,
    is_extracting,
    subtitle_file,
)

settings = get_settings()
router = APIRouter(tags=["subtitles"])

# Font cache directory
FONT_CACHE_DIR = Path("cache/fonts")
FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Lock to prevent parallel font extraction for same media_id
_font_extraction_locks: dict[int, asyncio.Lock] = {}
_background_tasks: set[asyncio.Task] = set()


def _cached(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


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
    cache_file = subtitle_file(media_id, track, format)
    if _cached(cache_file):
        logger.debug(f"Serving cached subtitle: {cache_file.name}")
        content = cache_file.read_bytes()
    else:
        # DB query to validate the track
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.media import MediaItem

        result = await session.execute(
            select(MediaItem).where(MediaItem.id == media_id).options(selectinload(MediaItem.streams))
        )
        media = result.scalar_one_or_none()
        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        if not any(
            s.codec_type == CodecType.SUBTITLE and s.stream_index == track for s in media.streams
        ):
            raise HTTPException(status_code=400, detail=f"Subtitle track {track} not found")

        # Double-check cache (the extraction may have finished during the query)
        if _cached(cache_file):
            content = cache_file.read_bytes()
        elif not is_extracting(media_id) and finished_recently(media_id):
            raise HTTPException(status_code=404, detail="Subtitle track could not be extracted")
        else:
            extraction_task(media_id)
            return JSONResponse(
                status_code=202,
                content={"status": "extracting", "retry_after": 2},
                headers={"Retry-After": "2"},
            )

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


@router.get("/{media_id}/status")
async def get_subtitle_status(
    media_id: int,
    track: int = Query(0),
    format: str = Query("ass"),
) -> dict:
    """Poll extraction status for a subtitle track."""
    if format not in ("ass", "srt"):
        raise HTTPException(status_code=400, detail="Format must be 'ass' or 'srt'")
    if _cached(subtitle_file(media_id, track, format)):
        return {"status": "ready"}
    if is_extracting(media_id):
        return {"status": "extracting"}
    if finished_recently(media_id):
        return {"status": "failed"}
    return {"status": "not_started"}


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
    # Check cache first. Resolve and compare parents so "..", or "..\" on a Windows
    # host (Starlette's path param only excludes "/"), can't read outside the cache.
    font_dir = (FONT_CACHE_DIR / str(media_id)).resolve()
    cache_file = (font_dir / filename).resolve()
    if cache_file.parent == font_dir and cache_file.is_file():
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
        from app.database import async_session_maker

        try:
            # Own session: the request's one is closed once this endpoint returns.
            # Same lock as get_fonts, so the player's request doesn't extract twice.
            async with (
                asyncio.timeout(120),  # 2 min max
                _font_extraction_locks.setdefault(media_id, asyncio.Lock()),
                async_session_maker() as s,
            ):
                if cache_dir.exists() and list(cache_dir.glob("*")):
                    return
                reader = await get_virtual_reader(s, media_id)
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

    # Fire and forget; keep a reference so the task isn't garbage-collected mid-run
    task = asyncio.create_task(extract_in_background())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"status": "warming", "media_id": media_id}
