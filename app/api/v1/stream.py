"""Streaming API endpoints for media playback."""

import bisect
import json
import re

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select

from app.api.deps import DBSession
from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.models.media import MediaItem
from app.services.ffmpeg import RemuxOptions, ffmpeg_remuxer
from app.services.mkv_cues import extract_keyframes_from_url
from app.services.streaming import get_virtual_reader, release_reader
from app.services.streaming.telegram import refresh_all_file_ids

settings = get_settings()
router = APIRouter()

RANGE_PATTERN = re.compile(r"bytes=(\d+)-(\d*)")


def parse_range_header(range_header: str | None, total_size: int) -> tuple[int, int]:
    """
    Parse HTTP Range header.

    Args:
        range_header: The Range header value (e.g., "bytes=0-1023")
        total_size: Total file size

    Returns:
        Tuple of (start, end) byte positions
    """
    if not range_header:
        return 0, total_size - 1

    match = RANGE_PATTERN.match(range_header)
    if not match:
        return 0, total_size - 1

    start = int(match.group(1))
    end_str = match.group(2)
    end = int(end_str) if end_str else total_size - 1

    # Clamp to valid range
    start = max(0, min(start, total_size - 1))
    end = max(start, min(end, total_size - 1))

    return start, end


@router.post("/warm/{media_id}")
async def warm_stream(
    media_id: int,
    session: DBSession,
) -> dict:
    """
    Pre-warm the Telegram file_id cache for faster playback start.

    Call this when user opens the video page (before play).
    This refreshes the file_id in background so stream starts instantly.
    """
    import time

    start = time.time()

    reader = await get_virtual_reader(session, media_id)
    if reader is None:
        raise HTTPException(status_code=404, detail="Media not found")

    logger.info(f"[WARM] media={media_id}, parts={len(reader._parts)}")

    # Force refresh of all file_ids
    try:
        if await reader._ensure_workers():
            await refresh_all_file_ids(reader._clients, reader._parts)
    finally:
        await reader._release_workers()

    elapsed = time.time() - start
    logger.info(f"[WARM] media={media_id} done in {elapsed:.2f}s")

    return {"status": "ok", "elapsed_ms": int(elapsed * 1000)}


@router.get("/raw/{media_id}")
async def stream_raw(
    media_id: int,
    request: Request,
    session: DBSession,
) -> StreamingResponse:
    """
    Stream raw media file bytes.

    This endpoint provides the raw MKV/MP4 bytes from Telegram.
    Supports HTTP Range requests for seeking.

    Used by:
    - FFmpeg for remuxing (Phase 4)
    - Direct download
    """
    # Persistent reader: cached across range requests for dynamic client scaling
    # First request: 1 client. Subsequent requests: tries to acquire more.
    reader = await get_virtual_reader(session, media_id, persistent=True)
    if reader is None:
        raise HTTPException(status_code=404, detail="Media not found")

    total_size = reader.total_size
    range_header = request.headers.get("range")
    logger.info(f"[RAW] media={media_id}, range={range_header}, size={total_size}, clients={len(reader._clients)}")

    range_start, range_end = parse_range_header(range_header, total_size)
    is_partial = range_header is not None

    status_code = 206 if is_partial else 200

    # Pool status for frontend warnings
    pool = worker_manager.pool_status()

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/x-matroska",
        # Anti-buffering headers for Cloudflare/nginx proxies
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
        # Pool status headers for frontend
        "X-Pool-Total": str(pool["total_clients"]),
        "X-Pool-In-Use": str(pool["clients_in_use"]),
        "X-Pool-Available": str(pool["clients_available"]),
        "X-Pool-Pressure": str(pool["pool_pressure"]),
        "X-Stream-Clients": str(len(reader._clients)),
    }

    if is_partial:
        headers["Content-Range"] = f"bytes {range_start}-{range_end}/{total_size}"

    async def stream_generator():
        """Generate stream chunks using persistent reader."""
        try:
            async for chunk in reader.read_range(range_start, range_end + 1):
                yield chunk
        except Exception:
            # Reader was force-released or connection dropped — end stream silently
            return

    return StreamingResponse(
        stream_generator(),
        status_code=status_code,
        headers=headers,
        media_type="video/x-matroska",
    )


@router.get("/pool-status")
async def pool_status() -> dict:
    """
    Lightweight pool status for frontend warnings.

    No DB session required — reads in-memory pool state.
    """
    return worker_manager.pool_status()


@router.post("/release/{media_id}")
async def stream_release(media_id: int) -> dict:
    """
    Release a cached stream reader and its Telegram clients.

    Called by the frontend when the player unmounts (user navigates away).
    This immediately frees the Telegram worker clients back to the pool.
    """
    await release_reader(media_id)
    logger.info(f"[RELEASE] Released stream reader for media {media_id}")
    return {"status": "ok"}


@router.head("/raw/{media_id}")
async def stream_head(
    media_id: int,
    session: DBSession,
) -> StreamingResponse:
    """
    HEAD request for stream metadata.

    Returns file size and supported features without body.
    Required by some players for seeking support.
    """
    reader = await get_virtual_reader(session, media_id)
    if reader is None:
        raise HTTPException(status_code=404, detail="Media not found")

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(reader.total_size),
        "Content-Type": "video/x-matroska",
    }

    return StreamingResponse(
        content=iter([]),
        status_code=200,
        headers=headers,
    )


async def _get_keyframe_for_time(session: DBSession, media_id: int, target_time: float) -> float:
    """
    Get keyframe timestamp for seeking using MKV Cues (fast: ~3MB read).

    1. Check if keyframes are cached in DB
    2. If cached, binary search (instant)
    3. If not, extract via MKV Cues and cache
    """
    if target_time <= 0:
        return 0.0

    # Query media item
    query = select(MediaItem).where(MediaItem.id == media_id)
    result = await session.execute(query)
    media = result.scalar_one_or_none()

    if not media:
        return target_time

    # Check cache
    if media.keyframes_index:
        try:
            keyframes = json.loads(media.keyframes_index)
            if keyframes:
                # Find keyframe closest to target (no pre-roll)
                # FFmpeg will start from this keyframe, video may start slightly after target
                idx = bisect.bisect_right(keyframes, target_time) - 1
                safe_idx = max(0, idx)
                if safe_idx >= 0:
                    keyframe = keyframes[safe_idx]
                    logger.debug(f"Seek: target={target_time}s -> keyframe={keyframe}s")
                    return keyframe
        except json.JSONDecodeError:
            pass

    # Extract via MKV Cues (fast: only reads ~3MB)
    logger.debug(f"Extracting keyframes for media {media_id}")
    base_url = f"http://127.0.0.1:{settings.app_port}"
    input_url = f"{base_url}/api/v1/stream/raw/{media_id}"

    keyframes = await extract_keyframes_from_url(input_url, total_size=media.total_size)

    if keyframes:
        media.keyframes_index = json.dumps(keyframes)
        await session.commit()
        logger.debug(f"Cached {len(keyframes)} keyframes for media {media_id}")

        # Find keyframe closest to target (no pre-roll)
        idx = bisect.bisect_right(keyframes, target_time) - 1
        safe_idx = max(0, idx)
        if safe_idx >= 0:
            return keyframes[safe_idx]

    return target_time


@router.head("/play/{media_id}")
async def stream_play_head(
    media_id: int,
    session: DBSession,
    audio: int = Query(0, description="Audio track index"),
    video: int = Query(0, description="Video track index"),
    t: float = Query(0, description="Start time in seconds"),
) -> StreamingResponse:
    """
    HEAD request for stream metadata including snap-to-keyframe time.

    Returns X-Stream-Start-Time header without starting the actual stream.
    Used by frontend to sync subtitles before playback.
    """
    reader = await get_virtual_reader(session, media_id)
    if reader is None:
        raise HTTPException(status_code=404, detail="Media not found")

    # Find keyframe using MKV Cues (fast: ~3MB read, then cached)
    actual_start_time = await _get_keyframe_for_time(session, media_id, t)

    return StreamingResponse(
        content=iter([]),
        status_code=200,
        headers={
            "Content-Type": "video/mp4",
            "X-Stream-Start-Time": str(actual_start_time),
            "X-Requested-Time": str(t),
            "Access-Control-Expose-Headers": "X-Stream-Start-Time, X-Requested-Time",
        },
    )


@router.get("/play/{media_id}")
async def stream_play(
    media_id: int,
    session: DBSession,
    audio: int = Query(0, description="Audio track index"),
    video: int = Query(0, description="Video track index"),
    t: float = Query(0, description="Start time in seconds"),
) -> StreamingResponse:
    """
    Stream browser-compatible video with snap-to-keyframe seeking.

    This endpoint remuxes the raw stream through FFmpeg:
    - Video: Copy (zero CPU)
    - Audio: Transcode to AAC (browser compatible)
    - Output: Fragmented MP4

    Seeking uses snap-to-keyframe strategy:
    - When seeking to time T, finds closest previous keyframe
    - Returns X-Stream-Start-Time header with actual start time
    - Frontend uses this to sync subtitles correctly

    Query params:
    - audio: Audio track index (default: 0)
    - video: Video track index (default: 0)
    - t: Start time in seconds for seeking (default: 0)
    """
    reader = await get_virtual_reader(session, media_id)
    if reader is None:
        raise HTTPException(status_code=404, detail="Media not found")

    logger.info(f"[PLAY] media={media_id}, audio={audio}, video={video}, t={t}")

    # Build internal URL for FFmpeg to read from
    base_url = f"http://127.0.0.1:{settings.app_port}"
    input_url = f"{base_url}/api/v1/stream/raw/{media_id}"

    # Get keyframe time for the requested position
    keyframe_time = await _get_keyframe_for_time(session, media_id, t)

    # Pre-seek 5 seconds before keyframe to give network time to buffer
    # This reduces initial freeze while maintaining accurate A/V sync
    pre_seek_buffer = 5.0
    pre_seek_time = max(0.0, keyframe_time - pre_seek_buffer)

    logger.info(
        f"[PLAY] media={media_id}, keyframe={keyframe_time:.2f}s, "
        f"pre_seek={pre_seek_time:.2f}s (requested t={t})"
    )

    options = RemuxOptions(
        video_stream=video,
        audio_stream=audio,
        start_time=keyframe_time if keyframe_time > 0 else None,
        pre_seek_time=pre_seek_time if pre_seek_time > 0 else None,
    )

    return StreamingResponse(
        ffmpeg_remuxer.stream(input_url, options),
        media_type="video/mp4",
        headers={
            "Content-Type": "video/mp4",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff",
            # Anti-buffering headers for Cloudflare/nginx proxies
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            # Tell frontend where stream actually starts
            "X-Stream-Start-Time": str(keyframe_time),
            # Tell frontend the original requested time for local seek
            "X-Requested-Time": str(t),
            "Access-Control-Expose-Headers": "X-Stream-Start-Time, X-Requested-Time",
        },
    )
