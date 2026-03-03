"""Season API endpoints — sub-resource of series."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, get_current_user
from app.models.media import Series
from app.models.user import User
from app.services.overrides import get_series_override, upsert_series_override
from app.services.tmdb import tmdb_client

router = APIRouter()


class SeasonPosterUpdateBody(BaseModel):
    poster_path: str


@router.get("/{series_id}/season/{season_number}")
async def get_season(session: DBSession, series_id: int, season_number: int) -> dict:
    """Get all episodes for a specific season."""
    query = (
        select(Series)
        .where(Series.id == series_id)
        .options(selectinload(Series.episodes))
    )
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    episodes = [
        ep for ep in series.episodes
        if ep.season_number == season_number
    ]
    episodes.sort(key=lambda e: e.episode_number or 0)

    if series.tmdb_id:
        await tmdb_client.get_season_episodes(series.tmdb_id, season_number)

    return {
        "series_id": series.id,
        "series_title": series.title,
        "season_number": season_number,
        "poster_path": episodes[0].poster_path if episodes else series.poster_path,
        "backdrop_path": series.backdrop_path,
        "episodes": [
            {
                "id": ep.id,
                "episode_number": ep.episode_number,
                "title": ep.title,
                "overview": ep.overview,
                "poster_path": ep.poster_path,
                "duration_seconds": ep.duration_seconds,
            }
            for ep in episodes
        ],
        "episodes_count": len(episodes),
    }


@router.patch("/{series_id}/season/{season_number}")
async def update_season(
    session: DBSession,
    series_id: int,
    season_number: int,
    body: SeasonPosterUpdateBody,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update poster for a specific season (per-user override)."""
    query = select(Series).where(Series.id == series_id)
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    override = await get_series_override(session, current_user, series_id)
    existing_posters = dict((override.season_posters or {}) if override else {})
    existing_posters[str(season_number)] = body.poster_path

    await upsert_series_override(
        session,
        current_user,
        series_id,
        season_posters=existing_posters,
    )

    logger.info(
        f"User {current_user.id} updated season {season_number} poster for series {series_id}"
    )

    return {
        "series_id": series.id,
        "season_number": season_number,
        "poster_path": body.poster_path,
    }


@router.get("/{series_id}/season/{season_number}/tmdb-images")
async def get_season_tmdb_images(
    session: DBSession, series_id: int, season_number: int
) -> dict:
    """Fetch available images from TMDB for a specific season."""
    query = select(Series).where(Series.id == series_id)
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    if not series.tmdb_id:
        return {"stills": [], "posters": [], "backdrops": []}

    images = await tmdb_client.get_season_images(series.tmdb_id, season_number)
    return {
        "stills": [],
        "posters": images.get("posters", []),
        "backdrops": [],
    }
