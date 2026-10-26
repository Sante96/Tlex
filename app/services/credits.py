"""Where a title's credits start: the player's Up next shows from there."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem

# A chapter named for the credits (anime call them the ending, "ED")
CREDITS_CHAPTER = re.compile(r"credit|ending|titoli|outro|\bED\b", re.IGNORECASE)


async def credits_start(session: AsyncSession, item: MediaItem) -> int | None:
    """Set by hand; else a credits chapter in the file's second half (not opening credits);
    else, for an episode, as far from the end as the nearest marked episode's (a series'
    credits keep their length); else None: the player shows Up next 30 s before the end.
    The item's chapters must be loaded."""
    if item.credits_start_seconds is not None:
        return item.credits_start_seconds
    duration = item.duration_seconds
    if not duration:
        return None
    for chapter in item.chapters or []:
        if CREDITS_CHAPTER.search(chapter.get("title") or "") and chapter["start"] >= duration / 2:
            return int(chapter["start"])
    if item.series_id is None:
        return None
    marked = (
        await session.execute(
            select(
                MediaItem.season_number,
                MediaItem.episode_number,
                MediaItem.duration_seconds,
                MediaItem.credits_start_seconds,
            ).where(
                MediaItem.series_id == item.series_id,
                MediaItem.id != item.id,
                MediaItem.credits_start_seconds.is_not(None),
                MediaItem.duration_seconds.is_not(None),
            )
        )
    ).all()
    if not marked:
        return None
    season, episode = item.season_number or 0, item.episode_number or 0
    nearest = min(
        marked,
        key=lambda m: (
            abs((m.season_number or 0) - season),
            abs((m.episode_number or 0) - episode),
        ),
    )
    start = duration - (nearest.duration_seconds - nearest.credits_start_seconds)
    return start if start >= duration / 2 else None
