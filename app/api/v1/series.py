"""Series API endpoints for TV show management."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, get_current_user_optional
from app.models.media import Series
from app.models.user import User, WatchProgress
from app.services.tmdb import tmdb_client

router = APIRouter()


@router.get("")
async def list_series(
    session: DBSession,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
) -> dict:
    """List all TV series with pagination."""
    offset = (page - 1) * page_size

    # Count total
    count_query = select(func.count()).select_from(Series)
    if search:
        count_query = count_query.where(Series.title.ilike(f"%{search}%"))
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get series with episode counts
    query = (
        select(Series)
        .options(selectinload(Series.episodes))
        .offset(offset)
        .limit(page_size)
        .order_by(Series.title)
    )
    if search:
        query = query.where(Series.title.ilike(f"%{search}%"))
    result = await session.execute(query)
    series_list = result.scalars().all()

    return {
        "items": [
            {
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
                "seasons_count": s.seasons_count,
                "episodes_count": s.episodes_count,
            }
            for s in series_list
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{series_id}")
async def get_series(
    session: DBSession,
    series_id: int,
    current_user: User | None = Depends(get_current_user_optional),
) -> dict:
    """Get series details with seasons."""
    query = (
        select(Series)
        .where(Series.id == series_id)
        .options(selectinload(Series.episodes))
    )
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    # Get watch progress for all episodes if user is authenticated
    watch_progress_map: dict[int, WatchProgress] = {}
    if current_user:
        episode_ids = [ep.id for ep in series.episodes]
        progress_query = select(WatchProgress).where(
            WatchProgress.user_id == current_user.id,
            WatchProgress.media_item_id.in_(episode_ids),
        )
        progress_result = await session.execute(progress_query)
        for wp in progress_result.scalars().all():
            watch_progress_map[wp.media_item_id] = wp

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
            "still_path": ep.poster_path,  # Episode thumbnail
            "duration_seconds": ep.duration_seconds,
            "watch_progress": None,
        }

        # Add watch progress if available
        if ep.id in watch_progress_map:
            wp = watch_progress_map[ep.id]
            ep_data["watch_progress"] = {
                "position_seconds": wp.position_seconds,
                "duration_seconds": wp.duration_seconds,
                "progress_percent": round((wp.position_seconds / wp.duration_seconds * 100) if wp.duration_seconds else 0, 1),
                "is_completed": wp.position_seconds >= wp.duration_seconds * 0.9 if wp.duration_seconds else False,
            }

        seasons_data[season_num]["episodes"].append(ep_data)

    # Sort episodes and fetch season posters from TMDB
    for season in seasons_data.values():
        season["episodes"].sort(key=lambda e: e["episode_number"] or 0)
        season["episodes_count"] = len(season["episodes"])

    # Fetch season posters from TMDB
    if series.tmdb_id:
        for season_num in seasons_data:
            season_details = await tmdb_client.get_season_details(
                series.tmdb_id, season_num
            )
            if season_details and season_details.get("poster_path"):
                seasons_data[season_num]["poster_path"] = season_details["poster_path"]
            else:
                # Fallback to series poster
                seasons_data[season_num]["poster_path"] = series.poster_path

    return {
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
    }


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

    # Filter episodes for this season
    episodes = [
        ep for ep in series.episodes
        if ep.season_number == season_number
    ]
    episodes.sort(key=lambda e: e.episode_number or 0)

    # Get season poster from TMDB if available
    if series.tmdb_id:
        season_data = await tmdb_client.get_season_episodes(series.tmdb_id, season_number)
        if season_data:
            # Season poster would need another API call, use first ep thumbnail for now
            pass

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


@router.post("/{series_id}/refresh-metadata")
async def refresh_series_metadata(session: DBSession, series_id: int) -> dict:
    """Refresh TMDB metadata for a series."""
    query = select(Series).where(Series.id == series_id)
    result = await session.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    # Search TMDB
    tmdb_result = await tmdb_client.search_tv(series.title)

    if not tmdb_result:
        raise HTTPException(
            status_code=404,
            detail=f"No TMDB results found for: {series.title}"
        )

    # Update series metadata
    old_title = series.title
    series.tmdb_id = tmdb_result.tmdb_id
    series.title = tmdb_result.title
    series.overview = tmdb_result.overview
    series.poster_path = tmdb_result.poster_path
    series.backdrop_path = tmdb_result.backdrop_path

    if tmdb_result.release_date:
        from datetime import date
        try:
            series.first_air_date = date.fromisoformat(tmdb_result.release_date)
        except ValueError:
            pass

    # Fetch and update extended metadata (genres, rating, content_rating)
    tv_details = await tmdb_client.get_tv_details(tmdb_result.tmdb_id)
    if tv_details:
        series.genres = ",".join(tv_details.genres) if tv_details.genres else None
        series.vote_average = tv_details.vote_average
        series.content_rating = tv_details.content_rating

    await session.commit()

    logger.info(f"Refreshed series metadata: '{old_title}' -> '{series.title}'")

    return {
        "message": f"Metadata refreshed for: {series.title}",
        "tmdb_id": tmdb_result.tmdb_id,
        "title": tmdb_result.title,
    }
