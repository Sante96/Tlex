"""Chapters of the titles scanned before chapters were stored.

A scan reads a new file's chapters with its tracks (ffprobe on the first MBs). Titles
already in the library are read once, in the background after startup: one at a time,
4 MB each, so they never hold the worker pool for long.
"""

import asyncio
import os
import tempfile

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.media import MediaItem
from app.services.ffprobe import ProbeResult, ffprobe_service
from app.services.streaming import get_virtual_reader

# An MKV keeps its chapters in the header: the scan's 4 MB covers them
HEAD_BYTES = 4 * 1024 * 1024
# Between two titles: viewers come first
PAUSE_SECONDS = 2


async def probe_head(session: AsyncSession, media_id: int) -> ProbeResult | None:
    """ffprobe on the first MBs of a title, read through a (non-persistent) reader."""
    reader = await get_virtual_reader(session, media_id)
    if reader is None:
        return None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mkv") as tmp:
        path = tmp.name
    try:
        with open(path, "wb") as f:
            async for chunk in reader.read_range(0, HEAD_BYTES):
                f.write(chunk)
        return await ffprobe_service.probe_file(path)
    finally:
        os.unlink(path)


async def backfill_chapters() -> int:
    """Read the chapters of every title never probed for them. Returns how many were."""
    async with async_session_maker() as session:
        ids = (
            (await session.execute(select(MediaItem.id).where(MediaItem.chapters.is_(None))))
            .scalars()
            .all()
        )
    if not ids:
        return 0
    logger.info(f"Reading the chapters of {len(ids)} titles")

    done = 0
    for media_id in ids:
        try:
            async with async_session_maker() as session:
                result = await probe_head(session, media_id)
                # A failure stays unprobed (NULL): tried again at the next start
                if result is not None:
                    item = await session.get(MediaItem, media_id)
                    if item is not None:
                        item.chapters = result.chapters
                        await session.commit()
                        done += 1
        except Exception as e:
            logger.warning(f"Chapters of media {media_id}: {e}")
        await asyncio.sleep(PAUSE_SECONDS)

    logger.info(f"Chapters read for {done}/{len(ids)} titles")
    return done
