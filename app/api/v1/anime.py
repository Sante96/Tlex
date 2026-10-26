"""The Anime section: Japanese animation, series and films together."""

from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DBSession
from app.models.media import MediaItem, MediaType, Series
from app.services.anime import anime

router = APIRouter()


@router.get("")
async def list_anime(
    session: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort: Literal["title", "recent"] = "recent",
) -> dict:
    """Anime series and films in one list: by title, or newest first (a series by its
    newest episode, as the Series section orders them)."""
    # ponytail: both lists whole, merged here; a few hundred anime at most. A UNION with
    # SQL paging if it ever grows past that
    newest_episode = (
        select(func.max(MediaItem.id)).where(MediaItem.series_id == Series.id).scalar_subquery()
    )
    seasons = (
        select(func.count(func.distinct(func.nullif(MediaItem.season_number, 0))))
        .where(MediaItem.series_id == Series.id)
        .scalar_subquery()
    )
    shows = (
        await session.execute(
            select(Series, newest_episode, seasons).where(anime(Series) == True)  # noqa: E712
        )
    ).all()
    films = (
        (
            await session.execute(
                select(MediaItem).where(
                    MediaItem.media_type == MediaType.MOVIE,
                    anime(MediaItem) == True,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    items = [
        {
            "kind": "series",
            "id": s.id,
            "title": s.title,
            "poster_path": s.poster_path,
            "backdrop_path": s.backdrop_path,
            "date": str(s.first_air_date) if s.first_air_date else None,
            "seasons_count": count or 0,
            "added": newest or 0,
        }
        for s, newest, count in shows
    ] + [
        {
            "kind": "movie",
            "id": f.id,
            "title": f.title,
            "poster_path": f.poster_path,
            "backdrop_path": f.backdrop_path,
            "date": str(f.release_date) if f.release_date else None,
            "seasons_count": None,
            "added": f.id,
        }
        for f in films
    ]
    if sort == "recent":
        items.sort(key=lambda i: -i["added"])
    else:
        items.sort(key=lambda i: i["title"].casefold())
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "total": len(items),
        "page": page,
        "page_size": page_size,
    }
