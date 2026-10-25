"""Subtitle and font extraction API endpoints."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from loguru import logger

from app.api.deps import DBSession
from app.config import get_settings
from app.models.media import CodecType
from app.services.subtitles.cache import (
    FONT_CACHE_DIR,
    extraction_task,
    finished_recently,
    is_extracting,
    pre_extract_fonts,
    subtitle_file,
)

settings = get_settings()
router = APIRouter(tags=["subtitles"])

# Lock to prevent parallel font extraction for same media_id
_font_extraction_locks: dict[int, asyncio.Lock] = {}


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
            select(MediaItem)
            .where(MediaItem.id == media_id)
            .options(selectinload(MediaItem.streams))
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


def _font_list(media_id: int) -> list[dict]:
    """The media's cached fonts with their names (parsed from the files: run in a thread)."""
    from app.services.subtitles import extract_font_names

    return [
        {
            "filename": f.name,
            "mimetype": "application/x-font-ttf",
            "size": f.stat().st_size,
            "url": f"/api/v1/subtitles/{media_id}/font/{f.name}",
            "names": extract_font_names(f.read_bytes()),
        }
        for f in sorted((FONT_CACHE_DIR / str(media_id)).glob("*"))
    ]


@router.get("/{media_id}/fonts")
async def get_fonts(
    media_id: int,
    session: DBSession,
) -> dict:
    """
    List the media's attached fonts, extracting them on first use.

    Use /{media_id}/font/{filename} to download one.
    """
    # Extracted once per media: its folder, left empty when the file has no fonts, then
    # answers without reading Telegram again (it was re-read on every subtitle toggle)
    async with _font_extraction_locks.setdefault(media_id, asyncio.Lock()):
        await pre_extract_fonts(media_id, session)
    fonts = await asyncio.to_thread(_font_list, media_id)
    return {"media_id": media_id, "fonts": fonts, "count": len(fonts)}


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
