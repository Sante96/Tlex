"""Anime: Japanese animation, a section of its own (TMDB says which, an admin can say
otherwise)."""

import asyncio

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType, Series
from app.services.tmdb import tmdb_client
from app.services.tmdb.models import MovieDetails, TVDetails


def anime(model: type[Series] | type[MediaItem]):
    """Whether a row is anime, in SQL: the admin's choice, else TMDB's."""
    return func.coalesce(model.anime_override, model.is_anime)


def apply_details(target: Series | MediaItem, details: TVDetails | MovieDetails) -> None:
    """TMDB's extended details on a series or a film."""
    target.genres = ",".join(details.genres) if details.genres else None
    target.vote_average = details.vote_average
    target.content_rating = details.content_rating
    target.original_language = details.original_language
    target.is_anime = details.anime


async def classify_library(session: AsyncSession) -> int:
    """Series and films never looked up on TMDB for their language (from before the Anime
    section; films never got their genres either): look them up, a few at a time."""
    shows = (
        (
            await session.execute(
                select(Series).where(
                    Series.tmdb_id.is_not(None), Series.original_language.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    films = (
        (
            await session.execute(
                select(MediaItem).where(
                    MediaItem.media_type == MediaType.MOVIE,
                    MediaItem.tmdb_id.is_not(None),
                    MediaItem.original_language.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    limit = asyncio.Semaphore(4)

    async def details(row: Series | MediaItem):
        async with limit:
            assert row.tmdb_id is not None
            if isinstance(row, Series):
                return await tmdb_client.get_tv_details(row.tmdb_id)
            return await tmdb_client.get_movie_full_details(row.tmdb_id)

    rows = [*shows, *films]
    found = await asyncio.gather(*(details(r) for r in rows))
    done = 0
    for row, info in zip(rows, found, strict=True):
        if info is not None:
            apply_details(row, info)
            done += 1
    await session.commit()
    if rows:
        anime_count = sum(1 for r in rows if r.is_anime)
        logger.info(f"[ANIME] Classified {done}/{len(rows)} titles from TMDB, {anime_count} anime")
    return done
