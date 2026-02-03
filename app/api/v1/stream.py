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
from app.database import async_session_maker
from app.models.media import MediaItem
from app.services.ffmpeg import RemuxOptions, ffmpeg_remuxer
from app.services.mkv_cues import extract_keyframes_from_url
from app.services.streaming import get_virtual_reader

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

    logger.debug(f"Warm: media={media_id}, parts={len(reader._parts)}")

    # Force refresh of all file_ids
    await reader._refresh_all_file_ids()



    elapsed = time.time() - start
    logger.debug(f"Pre-warmed cache for media {media_id} in {elapsed:.2f}s")

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
    # Get metadata using request session (will be closed after response starts)
    reader = await get_virtual_reader(session, media_id)
    if reader is None:
        raise HTTPException(status_code=404, detail="Media not found")

    total_size = reader.total_size
    range_header = request.headers.get("range")

    range_start, range_end = parse_range_header(range_header, total_size)
    is_partial = range_header is not None

    content_length = range_end - range_start + 1
    status_code = 206 if is_partial else 200

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": "video/x-matroska",
    }

    if is_partial:
        headers["Content-Range"] = f"bytes {range_start}-{range_end}/{total_size}"

    async def stream_generator():
        """Generate stream chunks with own session."""
        # Create a new session for the streaming duration
        async with async_session_maker() as stream_session:
            stream_reader = await get_virtual_reader(stream_session, media_id)
            if stream_reader is None:
                logger.error(f"Media {media_id} not found in stream generator")
                return

            try:
                async for chunk in stream_reader.read_range(range_start, range_end + 1):
                    yield chunk
            except Exception as e:
                logger.error(f"Stream error for media {media_id}: {e}")
                raise

    return StreamingResponse(
        stream_generator(),
        status_code=status_code,
        headers=headers,
        media_type="video/x-matroska",
    )


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

    # Build internal URL for FFmpeg to read from
    base_url = f"http://127.0.0.1:{settings.app_port}"
    input_url = f"{base_url}/api/v1/stream/raw/{media_id}"

    # Get keyframe time for the requested position
    keyframe_time = await _get_keyframe_for_time(session, media_id, t)

    # Pre-seek 5 seconds before keyframe to give network time to buffer
    # This reduces initial freeze while maintaining accurate A/V sync
    pre_seek_buffer = 5.0
    pre_seek_time = max(0.0, keyframe_time - pre_seek_buffer)

    logger.debug(f"Keyframe seek: req={t}s, keyframe={keyframe_time}s, pre_seek={pre_seek_time}s")

    options = RemuxOptions(
        video_stream=video,
        audio_stream=audio,
        start_time=keyframe_time if keyframe_time > 0 else None,
        pre_seek_time=pre_seek_time if pre_seek_time > 0 else None,
    )

    logger.debug(f"Starting playback: media={media_id}, audio={audio}, video={video}, t={keyframe_time}")

    return StreamingResponse(
        ffmpeg_remuxer.stream(input_url, options),
        media_type="video/mp4",
        headers={
            "Content-Type": "video/mp4",
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
            # Tell frontend where stream actually starts
            "X-Stream-Start-Time": str(keyframe_time),
            # Tell frontend the original requested time for local seek
            "X-Requested-Time": str(t),
            "Access-Control-Expose-Headers": "X-Stream-Start-Time, X-Requested-Time",
        },
    )
