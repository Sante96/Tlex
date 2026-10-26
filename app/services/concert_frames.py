"""A frame of the video as the image of a concert TMDB knows nothing about.

ffmpeg reads the backend's own /stream/raw (as the remux does) from halfway through, a
live's opening being black screens and logos, and keeps one frame. One concert at a
time, in the background: after startup and after a scan that added titles.
"""

import asyncio
import subprocess

from loguru import logger
from sqlalchemy import select

from app.config import get_settings
from app.core.security import INTERNAL_STREAM_TOKEN
from app.core.utils import find_ffmpeg, find_ffprobe
from app.database import async_session_maker
from app.models.media import MediaItem, MediaType
from app.services.images import ImageError, save_image

settings = get_settings()

FRAME_AT = 0.5  # of the duration
FALLBACK_AT = 300.0  # seconds in, when the duration couldn't be read
GRAB_TIMEOUT = 180  # a 4K HEVC title over Telegram: the seek plus one GOP
PROBE_TIMEOUT = 60
PAUSE_SECONDS = 2  # between two concerts: viewers come first
# PQ (HDR10, Dolby Vision's base layer) and HLG: tone-mapped to SDR, or the JPEG is grey
HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}
TONEMAP = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
)

_running = False
_again = False  # asked for while running: the running pass looks again before it ends
_tasks: set[asyncio.Task] = set()


async def _is_hdr(raw_url: str) -> bool:
    cmd = [
        find_ffprobe(),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=color_transfer",
        "-of",
        "csv=p=0",
        raw_url,
    ]
    try:
        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, timeout=PROBE_TIMEOUT
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.stdout.decode(errors="replace").strip() in HDR_TRANSFERS


async def grab_frame(media_id: int, at_seconds: float) -> bytes | None:
    """A JPEG of the frame at that time (the keyframe before it), 1280 px wide."""
    raw_url = (
        f"http://127.0.0.1:{settings.app_port}/api/v1/stream/raw/{media_id}"
        f"?internal={INTERNAL_STREAM_TOKEN}"
    )
    video_filter = (TONEMAP if await _is_hdr(raw_url) else "") + "scale=1280:-2"
    cmd = [
        find_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{at_seconds:.3f}",
        "-i",
        raw_url,
        "-frames:v",
        "1",
        "-vf",
        video_filter,
        "-f",
        "image2",
        "-c:v",
        "mjpeg",
        "-q:v",
        "3",
        "pipe:1",
    ]
    try:
        # A thread, not asyncio's subprocess: the dev backend also runs on Windows
        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, timeout=GRAB_TIMEOUT
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning(f"Frame of media {media_id}: {e}")
        return None
    if result.returncode != 0 or not result.stdout:
        error = result.stderr.decode(errors="replace").strip()[-300:]
        logger.warning(f"Frame of media {media_id} failed: {error}")
        return None
    return result.stdout


async def _one_pass() -> int:
    """A frame for every concert without a backdrop: a frame is wide, the card's
    picture; the poster (tall) is the franchise's unless one is chosen."""
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(MediaItem.id, MediaItem.duration_seconds).where(
                    MediaItem.media_type == MediaType.CONCERT,
                    MediaItem.backdrop_path.is_(None),
                )
            )
        ).all()

    done = 0
    for media_id, duration in rows:
        # A failure leaves it as it was: tried again on the next pass
        at = duration * FRAME_AT if duration else FALLBACK_AT
        data = await grab_frame(media_id, at)
        if data:
            try:
                path = save_image(data)
            except ImageError as e:
                logger.warning(f"Frame of media {media_id}: {e}")
                continue
            async with async_session_maker() as session:
                item = await session.get(MediaItem, media_id)
                # An image someone chose meanwhile wins
                if item is not None and item.backdrop_path is None:
                    item.backdrop_path = path
                    await session.commit()
                    done += 1
        await asyncio.sleep(PAUSE_SECONDS)
    if rows:
        logger.info(f"Concert frames: {done}/{len(rows)}")
    return done


async def backfill_concert_frames() -> int:
    """Give every concert without an image a frame. Returns how many got one."""
    global _running, _again
    if _running:  # a scan finished during this pass: it looks again before ending
        _again = True
        return 0
    _running = True
    try:
        done = 0
        while True:
            _again = False
            done += await _one_pass()
            if not _again:
                return done
    finally:
        _running = False


async def _backfill_logged() -> None:
    try:
        await backfill_concert_frames()
    except Exception as e:
        logger.warning(f"Concert frames failed: {e}")


def schedule_concert_frames() -> None:
    """Run the frames pass in the background (kept referenced until it ends)."""
    task = asyncio.create_task(_backfill_logged())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
