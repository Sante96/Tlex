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
from app.core.utils import find_ffmpeg
from app.database import async_session_maker
from app.models.media import MediaItem, MediaType
from app.services.images import ImageError, save_image

settings = get_settings()

FRAME_AT = 0.5  # of the duration
GRAB_TIMEOUT = 180  # a 4K HEVC title over Telegram: the seek plus one GOP
PAUSE_SECONDS = 2  # between two concerts: viewers come first

_running = False
_tasks: set[asyncio.Task] = set()


async def grab_frame(media_id: int, at_seconds: float) -> bytes | None:
    """A JPEG of the frame at that time (the keyframe before it), 1280 px wide."""
    raw_url = (
        f"http://127.0.0.1:{settings.app_port}/api/v1/stream/raw/{media_id}"
        f"?internal={INTERNAL_STREAM_TOKEN}"
    )
    # ponytail: no tone mapping, an HDR concert gives a washed-out frame; add zscale
    # tonemap when one turns up
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
        "scale=1280:-2",
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


async def backfill_concert_frames() -> int:
    """Give every concert without an image a frame. Returns how many got one."""
    global _running
    if _running:  # a scan finished while startup's run was still going
        return 0
    _running = True
    try:
        async with async_session_maker() as session:
            rows = (
                await session.execute(
                    select(MediaItem.id, MediaItem.duration_seconds).where(
                        MediaItem.media_type == MediaType.CONCERT,
                        MediaItem.poster_path.is_(None),
                        MediaItem.duration_seconds.is_not(None),
                    )
                )
            ).all()

        done = 0
        for media_id, duration in rows:
            # A failure leaves it without an image: tried again on the next run
            data = await grab_frame(media_id, duration * FRAME_AT)
            if data:
                try:
                    path = save_image(data)
                except ImageError as e:
                    logger.warning(f"Frame of media {media_id}: {e}")
                    continue
                async with async_session_maker() as session:
                    item = await session.get(MediaItem, media_id)
                    # Someone may have chosen an image meanwhile: it wins
                    if item is not None and item.poster_path is None:
                        item.poster_path = path
                        item.backdrop_path = item.backdrop_path or path
                        await session.commit()
                        done += 1
            await asyncio.sleep(PAUSE_SECONDS)
        if rows:
            logger.info(f"Concert frames: {done}/{len(rows)}")
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
