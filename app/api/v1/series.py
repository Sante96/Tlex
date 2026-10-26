"""Series API endpoints for TV show management."""

import asyncio
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import (
    DBSession,
    get_admin_user,
    get_current_profile,
    get_current_user,
    get_current_user_optional,
)
from app.models.media import MediaItem, Series
from app.models.user import Profile, User, WatchProgress
from app.services.anime import anime, apply_details
from app.services.overrides import (
    apply_series_override,
    get_media_overrides,
    get_series_override,
    get_series_overrides,
    upsert_series_override,
)
from app.services.tmdb import tmdb_client


class SeriesUpdateBody(BaseModel):
    title: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    first_air_date: str | None = None


router = APIRouter()


@router.get("")
async def list_series(
    session: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str | None = None,
    sort: Literal["title", "recent"] = "title",
    anime_only: bool | None = Query(None, alias="anime"),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict:
    """List all TV series with pagination, by title or by their newest episode; anime=false
    leaves the anime out (the Series section), true keeps only them."""
    offset = (page - 1) * page_size

    # Count total
    count_query = select(func.count()).select_from(Series)
    if search:
        count_query = count_query.where(Series.title.ilike(f"%{search}%"))
    if anime_only is not None:
        count_query = count_query.where(anime(Series) == anime_only)
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    if sort == "recent":
        newest_episode = (
            select(func.max(MediaItem.id)).where(MediaItem.series_id == Series.id).scalar_subquery()
        )
        order = newest_episode.desc().nulls_last()
    else:
        order = Series.title
    query = select(Series).offset(offset).limit(page_size).order_by(order)
    if search:
        query = query.where(Series.title.ilike(f"%{search}%"))
    if anime_only is not None:
        query = query.where(anime(Series) == anime_only)
    result = await session.execute(query)
    series_list = result.scalars().all()

    # Season/episode counts in SQL, instead of loading every episode just to count it.
    # Seasons as Series.seasons counts them: distinct, ignoring None and 0
    counts_result = await session.execute(
        select(
            MediaItem.series_id,
            func.count(func.distinct(func.nullif(MediaItem.season_number, 0))),
            func.count(MediaItem.id),
            func.max(MediaItem.id),
        )
        .where(MediaItem.series_id.in_([s.id for s in series_list]))
        .group_by(MediaItem.series_id)
    )
    # And the newest episode's id: the home compares it with films' ids, newest first
    counts = {
        series_id: (seasons, episodes, latest)
        for series_id, seasons, episodes, latest in counts_result.all()
    }

    # Fetch per-user overrides
    overrides_map: dict = {}
    if current_user:
        overrides_map = await get_series_overrides(
            session, current_user, [s.id for s in series_list]
        )

    items = []
    for s in series_list:
        item_data = {
            "id": s.id,
            "tmdb_id": s.tmdb_id,
            "title": s.title,
            "overview": s.overview,
            "poster_path": s.poster_path,
            "backdrop_path": s.backdrop_path,
            "first_air_date": str(s.first_air_date) if s.first_air_date else None,
            "genres": s.genres.split(",") if s.genres else [],
            "vote_average": s.vote_average,
            "content_rating": s.content_rating,
            "seasons_count": counts.get(s.id, (0, 0, None))[0],
            "episodes_count": counts.get(s.id, (0, 0, None))[1],
            "latest_media_id": counts.get(s.id, (0, 0, None))[2],
        }
        apply_series_override(item_data, overrides_map.get(s.id))
        items.append(item_data)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{series_id}")
async def get_series(
    request: Request,
    session: DBSession,
    series_id: int,
    current_user: User | None = Depends(get_current_user_optional),
    profile: Profile = Depends(get_current_profile),
) -> dict:
    """Get series details with seasons, and the current profile's progress."""
    query = select(Series).where(Series.id == series_id).options(selectinload(Series.episodes))
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    # The profile's watch progress for every episode
    watch_progress_map: dict[int, WatchProgress] = {}
    episode_ids = [ep.id for ep in series.episodes]
    progress_query = select(WatchProgress).where(
        WatchProgress.profile_id == profile.id,
        WatchProgress.media_item_id.in_(episode_ids),
    )
    progress_result = await session.execute(progress_query)
    for wp in progress_result.scalars().all():
        watch_progress_map[wp.media_item_id] = wp
    # The user's own stills (an episode's Edit): the list showed TMDB's all the same
    own_stills = (
        {
            media_id: o.poster_path
            for media_id, o in (
                await get_media_overrides(session, current_user, episode_ids)
            ).items()
            if o.poster_path
        }
        if current_user
        else {}
    )

    # Group episodes by season
    seasons_data = {}
    for ep in series.episodes:
        season_num = ep.season_number if ep.season_number is not None else 1
        if season_num not in seasons_data:
            seasons_data[season_num] = {
                "season_number": season_num,
                "episodes": [],
                "poster_path": None,  # Will be fetched from TMDB
            }

        # Build episode data with watch progress
        ep_data = {
            "id": ep.id,
            "episode_number": ep.episode_number,
            "title": ep.title,
            "overview": ep.overview,
            "still_path": own_stills.get(ep.id) or ep.poster_path,  # Episode thumbnail
            "release_date": str(ep.release_date) if ep.release_date else None,
            "duration_seconds": ep.duration_seconds,
            "watch_progress": None,
        }

        # Add watch progress if available
        if ep.id in watch_progress_map:
            wp = watch_progress_map[ep.id]
            ep_data["watch_progress"] = {
                "position_seconds": wp.position_seconds,
                "duration_seconds": wp.duration_seconds,
                "progress_percent": round(
                    (wp.position_seconds / wp.duration_seconds * 100) if wp.duration_seconds else 0,
                    1,
                ),
                "is_completed": wp.position_seconds >= wp.duration_seconds * 0.9
                if wp.duration_seconds
                else False,
            }

        seasons_data[season_num]["episodes"].append(ep_data)

    # Sort episodes and fetch season posters from TMDB
    for season in seasons_data.values():
        season["episodes"].sort(key=lambda e: e["episode_number"] or 0)
        season["episodes_count"] = len(season["episodes"])

    # Apply season poster overrides, then TMDB fallback, then series poster
    poster_overrides = series.season_posters or {}
    # TMDB posters for the seasons without an override, all requested at once
    lang = request.headers.get("Accept-Language", "it-IT")
    tmdb_id = series.tmdb_id
    from_tmdb = [n for n in seasons_data if not poster_overrides.get(str(n))] if tmdb_id else []
    details = (
        await asyncio.gather(
            *(tmdb_client.get_season_details(tmdb_id, n, language=lang) for n in from_tmdb)
        )
        if tmdb_id
        else []
    )
    tmdb_posters = {n: d.get("poster_path") for n, d in zip(from_tmdb, details, strict=True) if d}
    for season_num in seasons_data:
        seasons_data[season_num]["poster_path"] = (
            poster_overrides.get(str(season_num))
            or tmdb_posters.get(season_num)
            or series.poster_path
        )

    # Merge per-user overrides
    series_override = None
    if current_user:
        series_override = await get_series_override(session, current_user, series_id)

    # Apply per-user season poster overrides
    if series_override and series_override.season_posters:
        user_season_posters = series_override.season_posters
        for season_num_str, poster in user_season_posters.items():
            sn = int(season_num_str)
            if sn in seasons_data:
                seasons_data[sn]["poster_path"] = poster

    detail_data = {
        "id": series.id,
        "tmdb_id": series.tmdb_id,
        "title": series.title,
        "overview": series.overview,
        "poster_path": series.poster_path,
        "backdrop_path": series.backdrop_path,
        "first_air_date": str(series.first_air_date) if series.first_air_date else None,
        "genres": series.genres.split(",") if series.genres else [],
        "vote_average": series.vote_average,
        "content_rating": series.content_rating,
        "seasons": sorted(seasons_data.values(), key=lambda s: s["season_number"]),
        "seasons_count": len(seasons_data),
        "episodes_count": series.episodes_count,
        "is_anime": series.anime_override if series.anime_override is not None else series.is_anime,
        "anime_override": series.anime_override,
    }
    apply_series_override(detail_data, series_override)

    return detail_data


@router.get("/{series_id}/cast")
async def get_series_cast(session: DBSession, series_id: int) -> list:
    """Get cast for a TV series from TMDB."""
    query = select(Series).where(Series.id == series_id)
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    if not series.tmdb_id:
        return []

    # Get credits from TMDB
    credits = await tmdb_client.get_tv_credits(series.tmdb_id)
    return credits


@router.get("/{series_id}/trailer")
async def get_series_trailer(session: DBSession, series_id: int) -> dict:
    """Get YouTube trailer key for a TV series from TMDB."""
    query = select(Series).where(Series.id == series_id)
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series or not series.tmdb_id:
        return {"key": None}

    key = await tmdb_client.get_trailer(series.tmdb_id, "tv")
    return {"key": key}


class AnimeUpdate(BaseModel):
    anime: bool | None = None


@router.put("/{series_id}/anime")
async def set_series_anime(
    session: DBSession,
    series_id: int,
    body: AnimeUpdate,
    _admin=Depends(get_admin_user),
) -> dict:
    """Anime or not, whatever TMDB says; None goes back to TMDB's."""
    series = await session.get(Series, series_id)
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    series.anime_override = body.anime
    await session.commit()
    return {"anime_override": body.anime}


@router.patch("/{series_id}")
async def update_series(
    session: DBSession,
    series_id: int,
    body: SeriesUpdateBody,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update visual metadata for a TV series (per-user override)."""
    query = select(Series).where(Series.id == series_id)
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    override = await upsert_series_override(
        session,
        current_user,
        series_id,
        poster_path=body.poster_path,
        backdrop_path=body.backdrop_path,
    )

    logger.info(f"User {current_user.id} updated series override for {series_id}")

    return {
        "id": series.id,
        "title": series.title,
        "overview": series.overview,
        "poster_path": override.poster_path or series.poster_path,
        "backdrop_path": override.backdrop_path or series.backdrop_path,
        "first_air_date": str(series.first_air_date) if series.first_air_date else None,
    }


@router.get("/{series_id}/tmdb-images")
async def get_series_tmdb_images(session: DBSession, series_id: int) -> dict:
    """Fetch available images from TMDB for a TV series."""
    query = select(Series).where(Series.id == series_id)
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    if not series.tmdb_id:
        return {"stills": [], "posters": [], "backdrops": []}

    images = await tmdb_client.get_tv_images(series.tmdb_id)
    return {
        "stills": [],
        "posters": images.get("posters", []),
        "backdrops": images.get("backdrops", []),
    }


@router.post("/{series_id}/refresh-metadata")
async def refresh_series_metadata(
    request: Request,
    session: DBSession,
    series_id: int,
    _admin=Depends(get_admin_user),
) -> dict:
    """Refresh TMDB metadata for a series."""
    query = select(Series).where(Series.id == series_id)
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    # Search TMDB
    lang = request.headers.get("Accept-Language", "it-IT")
    tmdb_result = await tmdb_client.search_tv(series.title, language=lang)

    if not tmdb_result:
        raise HTTPException(status_code=404, detail=f"No TMDB results found for: {series.title}")

    # Update series metadata
    old_title = series.title
    series.tmdb_id = tmdb_result.tmdb_id
    series.title = tmdb_result.title
    series.overview = tmdb_result.overview
    series.poster_path = tmdb_result.poster_path
    series.backdrop_path = tmdb_result.backdrop_path

    if tmdb_result.release_date:
        try:
            series.first_air_date = date.fromisoformat(tmdb_result.release_date)
        except ValueError:
            pass

    # Fetch and update extended metadata (genres, rating, content_rating)
    tv_details = await tmdb_client.get_tv_details(tmdb_result.tmdb_id, language=lang)
    if tv_details:
        apply_details(series, tv_details)

    # Refresh episode titles and overviews from TMDB
    ep_query = select(MediaItem).where(MediaItem.series_id == series.id)
    ep_result = await session.execute(ep_query)
    episodes = ep_result.scalars().all()

    # Group episodes by season to minimise TMDB requests
    seasons_needed: set[int] = {ep.season_number for ep in episodes if ep.season_number is not None}
    tmdb_episodes: dict[tuple[int, int], str | None] = {}  # (season, ep) -> title
    tmdb_overviews: dict[tuple[int, int], str | None] = {}
    tmdb_stills: dict[tuple[int, int], str | None] = {}

    for season_num in seasons_needed:
        tmdb_season_eps = await tmdb_client.get_season_episodes(
            tmdb_result.tmdb_id, season_num, language=lang
        )
        for ep_info in tmdb_season_eps:
            key = (season_num, ep_info.episode_number)
            tmdb_episodes[key] = ep_info.name
            tmdb_overviews[key] = ep_info.overview
            tmdb_stills[key] = ep_info.still_path

    updated_eps = 0
    for ep in episodes:
        # The series' entry, and its backdrop: matched to another show, the episodes kept
        # the old one's
        ep.tmdb_id = tmdb_result.tmdb_id
        ep.backdrop_path = tmdb_result.backdrop_path
        if ep.season_number is None or ep.episode_number is None:
            continue
        key = (ep.season_number, ep.episode_number)
        if key in tmdb_episodes:
            if title := tmdb_episodes[key]:
                ep.title = title
            if overview := tmdb_overviews[key]:
                ep.overview = overview
            # An episode's still is stored as its poster (as the scan does)
            if still := tmdb_stills[key]:
                ep.poster_path = still
            updated_eps += 1

    await session.commit()

    logger.info(
        f"Refreshed series metadata: '{old_title}' -> '{series.title}' ({updated_eps} episodes updated)"
    )

    return {
        "message": f"Metadata refreshed for: {series.title}",
        "tmdb_id": tmdb_result.tmdb_id,
        "title": tmdb_result.title,
    }
