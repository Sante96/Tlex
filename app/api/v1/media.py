"""Media library API endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, get_admin_user, get_current_user, get_current_user_optional
from app.core.worker_manager import worker_manager
from app.models.media import MediaItem, MediaStream, MediaType
from app.models.user import User
from app.schemas import (
    MediaItemDetailResponse,
    MediaItemResponse,
    MediaListResponse,
    MediaPartResponse,
    MediaStreamResponse,
)
from app.services.ffprobe import ffprobe_service
from app.services.overrides import (
    apply_media_override,
    get_media_override,
    get_media_overrides,
    upsert_media_override,
)
from app.services.tmdb import tmdb_client

router = APIRouter()


@router.get("", response_model=MediaListResponse)
async def list_media(
    session: DBSession,
    page: int = 1,
    page_size: int = 20,
    media_type: MediaType | None = None,
    search: str | None = None,
    current_user: User | None = Depends(get_current_user_optional),
) -> MediaListResponse:
    """List all media items with pagination."""
    offset = (page - 1) * page_size

    # Base query
    query = select(MediaItem).options(selectinload(MediaItem.parts))

    if media_type:
        query = query.where(MediaItem.media_type == media_type)
    if search:
        query = query.where(MediaItem.title.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(MediaItem)
    if media_type:
        count_query = count_query.where(MediaItem.media_type == media_type)
    if search:
        count_query = count_query.where(MediaItem.title.ilike(f"%{search}%"))
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get items
    query = query.offset(offset).limit(page_size).order_by(MediaItem.title)
    result = await session.execute(query)
    items = result.scalars().all()

    # Fetch per-user overrides
    overrides_map: dict = {}
    if current_user:
        overrides_map = await get_media_overrides(
            session, current_user, [item.id for item in items]
        )

    response_items = []
    for item in items:
        item_data = {
            "id": item.id,
            "tmdb_id": item.tmdb_id,
            "title": item.title,
            "overview": item.overview,
            "poster_path": item.poster_path,
            "backdrop_path": item.backdrop_path,
            "release_date": str(item.release_date) if item.release_date else None,
            "media_type": item.media_type.value,
            "duration_seconds": item.duration_seconds,
            "season_number": item.season_number,
            "episode_number": item.episode_number,
            "total_size": item.total_size,
            "parts_count": len(item.parts),
        }
        apply_media_override(item_data, overrides_map.get(item.id))
        response_items.append(MediaItemResponse(**item_data))

    return MediaListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{media_id}", response_model=MediaItemDetailResponse)
async def get_media(
    session: DBSession,
    media_id: int,
    current_user: User | None = Depends(get_current_user_optional),
) -> MediaItemDetailResponse:
    """Get detailed media item by ID."""
    query = (
        select(MediaItem)
        .where(MediaItem.id == media_id)
        .options(
            selectinload(MediaItem.parts),
            selectinload(MediaItem.streams),
            selectinload(MediaItem.series),
        )
    )
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    # For movies: vote_average, genres, content_rating live on MediaItem
    # For episodes: fall back to Series
    series = item.series
    if item.media_type == MediaType.MOVIE:
        vote_average = item.vote_average
        genres_raw = item.genres
        content_rating = item.content_rating
    else:
        vote_average = series.vote_average if series else None
        genres_raw = series.genres if series else None
        content_rating = item.content_rating or (series.content_rating if series else None)
    genres = genres_raw.split(",") if genres_raw else None

    # Merge per-user overrides
    override = None
    if current_user:
        override = await get_media_override(session, current_user, media_id)

    detail_data = {
        "id": item.id,
        "tmdb_id": item.tmdb_id,
        "title": item.title,
        "overview": item.overview,
        "poster_path": item.poster_path,
        "backdrop_path": item.backdrop_path,
        "release_date": str(item.release_date) if item.release_date else None,
        "media_type": item.media_type.value,
        "duration_seconds": item.duration_seconds,
        "series_id": item.series_id,
        "season_number": item.season_number,
        "episode_number": item.episode_number,
        "total_size": item.total_size,
        "parts_count": len(item.parts),
        "vote_average": vote_average,
        "genres": genres,
        "content_rating": content_rating,
    }
    apply_media_override(detail_data, override)

    return MediaItemDetailResponse(
        **detail_data,
        parts=[
            MediaPartResponse(
                id=p.id,
                part_index=p.part_index,
                file_size=p.file_size,
            )
            for p in sorted(item.parts, key=lambda x: x.part_index)
        ],
        streams=[
            MediaStreamResponse(
                id=s.id,
                stream_index=s.stream_index,
                codec_type=s.codec_type.value,
                codec_name=s.codec_name,
                language=s.language,
                title=s.title,
                is_default=s.is_default,
            )
            for s in item.streams
        ],
    )


class NextEpisodeResponse(BaseModel):
    """Response for next episode lookup."""

    id: int
    title: str
    season_number: int | None
    episode_number: int | None
    duration_seconds: int | None
    poster_path: str | None
    backdrop_path: str | None
    still_path: str | None = None


@router.get("/{media_id}/next", response_model=NextEpisodeResponse | None)
async def get_next_episode(
    session: DBSession,
    media_id: int,
):
    """Get the next episode after the given media item."""
    # Load current item
    result = await session.execute(
        select(MediaItem).where(MediaItem.id == media_id)
    )
    current = result.scalar_one_or_none()
    if not current or current.media_type != MediaType.EPISODE or not current.series_id:
        return None

    # Try next episode in same season
    next_in_season = await session.execute(
        select(MediaItem)
        .where(
            MediaItem.series_id == current.series_id,
            MediaItem.season_number == current.season_number,
            MediaItem.episode_number > (current.episode_number or 0),
        )
        .order_by(MediaItem.episode_number.asc())
        .limit(1)
    )
    next_ep = next_in_season.scalar_one_or_none()

    # If no more in season, try first episode of next season
    if not next_ep:
        next_season = await session.execute(
            select(MediaItem)
            .where(
                MediaItem.series_id == current.series_id,
                MediaItem.season_number > (current.season_number or 0),
            )
            .order_by(MediaItem.season_number.asc(), MediaItem.episode_number.asc())
            .limit(1)
        )
        next_ep = next_season.scalar_one_or_none()

    if not next_ep:
        return None

    # Episode thumbnail: scanner stores TMDB still in poster_path (same as series endpoint)
    still_path = next_ep.poster_path

    return NextEpisodeResponse(
        id=next_ep.id,
        title=next_ep.title,
        season_number=next_ep.season_number,
        episode_number=next_ep.episode_number,
        duration_seconds=next_ep.duration_seconds,
        poster_path=next_ep.poster_path,
        backdrop_path=next_ep.backdrop_path,
        still_path=still_path,
    )


@router.delete("/{media_id}")
async def delete_media(
    session: DBSession,
    media_id: int,
    _admin=Depends(get_admin_user),
) -> dict:
    """Delete a media item."""
    query = select(MediaItem).where(MediaItem.id == media_id)
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    await session.delete(item)
    await session.commit()

    return {"message": f"Deleted media: {item.title}"}


@router.post("/{media_id}/analyze")
async def analyze_media(
    session: DBSession,
    media_id: int,
    _admin=Depends(get_admin_user),
) -> dict:
    """Re-analyze a media item to extract duration and streams."""
    query = (
        select(MediaItem)
        .where(MediaItem.id == media_id)
        .options(selectinload(MediaItem.parts))
    )
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    if not item.parts:
        raise HTTPException(status_code=400, detail="Media has no parts")

    # Get a worker
    worker_result = await worker_manager.get_best_worker(session)
    if not worker_result:
        raise HTTPException(status_code=503, detail="No workers available")

    worker, client = worker_result
    first_part = sorted(item.parts, key=lambda p: p.part_index)[0]

    try:
        logger.info(f"Analyzing: {item.title}")

        # Refresh file_id from original message (handles FILE_REFERENCE_EXPIRED)
        file_id = first_part.telegram_file_id
        if first_part.channel_id and first_part.message_id:
            try:
                # Populate peer cache for this specific channel
                await client.get_chat(first_part.channel_id)

                messages = await client.get_messages(
                    first_part.channel_id,
                    message_ids=first_part.message_id,
                )
                if messages and messages.document:
                    file_id = messages.document.file_id
                    # Update in DB for future use
                    first_part.telegram_file_id = file_id
                    logger.info("Refreshed file_id from original message")
            except Exception as refresh_err:
                logger.warning(f"Could not refresh file_id: {refresh_err}")

        probe_result = await ffprobe_service.analyze_from_telegram(
            client, file_id
        )

        if probe_result:
            # MKV/MP4 header contains total duration, no estimation needed
            if probe_result.duration_seconds:
                item.duration_seconds = probe_result.duration_seconds
                logger.info(f"Duration from header: {item.duration_seconds}s")

            # Clear existing streams and add new ones
            # Refresh to avoid greenlet error after Pyrogram operations
            await session.refresh(item, ["streams"])
            for stream in item.streams:
                await session.delete(stream)

            for stream_info in probe_result.streams:
                stream = MediaStream(
                    media_item_id=item.id,
                    stream_index=stream_info.stream_index,
                    codec_type=stream_info.codec_type,
                    codec_name=stream_info.codec_name,
                    language=stream_info.language,
                    title=stream_info.title,
                    is_default=stream_info.is_default,
                )
                session.add(stream)

            await session.commit()

            return {
                "message": f"Analyzed: {item.title}",
                "duration_seconds": probe_result.duration_seconds,
                "streams_count": len(probe_result.streams),
            }
        else:
            raise HTTPException(status_code=500, detail="FFprobe analysis failed")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post("/{media_id}/refresh-metadata")
async def refresh_metadata(
    session: DBSession,
    media_id: int,
    _admin=Depends(get_admin_user),
) -> dict:
    """
    Refresh TMDB metadata for a media item.

    Only updates poster, backdrop, overview, release_date from TMDB.
    Does not re-scan Telegram or re-analyze streams.
    """
    query = select(MediaItem).where(MediaItem.id == media_id)
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    old_title = item.title

    if item.media_type == MediaType.MOVIE:
        # For movies: first find tmdb_id via search, then fetch full details
        tmdb_result = await tmdb_client.search_movie(item.title)
        if not tmdb_result:
            raise HTTPException(
                status_code=404, detail=f"No TMDB results found for: {item.title}"
            )
        movie_details = await tmdb_client.get_movie_full_details(tmdb_result.tmdb_id)
        if movie_details:
            item.tmdb_id = movie_details.tmdb_id
            item.title = movie_details.title
            item.overview = movie_details.overview
            item.poster_path = movie_details.poster_path
            item.backdrop_path = movie_details.backdrop_path
            item.vote_average = movie_details.vote_average
            item.genres = ",".join(movie_details.genres) if movie_details.genres else None
            item.content_rating = movie_details.content_rating
            if movie_details.release_date:
                try:
                    item.release_date = date.fromisoformat(movie_details.release_date)
                except ValueError:
                    pass
        else:
            item.tmdb_id = tmdb_result.tmdb_id
            item.title = tmdb_result.title
            item.overview = tmdb_result.overview
            item.poster_path = tmdb_result.poster_path
            item.backdrop_path = tmdb_result.backdrop_path
    else:
        tmdb_result = await tmdb_client.search_tv(
            item.title, item.season_number, item.episode_number
        )
        if not tmdb_result:
            raise HTTPException(
                status_code=404, detail=f"No TMDB results found for: {item.title}"
            )
        item.tmdb_id = tmdb_result.tmdb_id
        item.title = tmdb_result.title
        item.overview = tmdb_result.overview
        item.poster_path = tmdb_result.poster_path
        item.backdrop_path = tmdb_result.backdrop_path
        if tmdb_result.release_date:
            try:
                item.release_date = date.fromisoformat(tmdb_result.release_date)
            except ValueError:
                pass

    await session.commit()
    logger.info(f"Refreshed metadata: '{old_title}' -> '{item.title}'")

    return {
        "message": f"Metadata refreshed for: {item.title}",
        "tmdb_id": item.tmdb_id,
        "title": item.title,
        "poster_path": item.poster_path,
    }


@router.get("/{media_id}/cast")
async def get_media_cast(session: DBSession, media_id: int) -> list[dict]:
    """Get cast and crew for a media item from TMDB."""
    query = select(MediaItem).where(MediaItem.id == media_id)
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    if not item.tmdb_id:
        return []

    # Get credits from TMDB
    if item.media_type == MediaType.EPISODE:
        credits = await tmdb_client.get_tv_credits(item.tmdb_id)
    else:
        credits = await tmdb_client.get_movie_credits(item.tmdb_id)

    return [
        {
            "id": c.id,
            "name": c.name,
            "character": c.character,
            "job": c.job,
            "profile_path": c.profile_path,
            "order": c.order,
        }
        for c in credits
    ]


class MediaUpdateBody(BaseModel):
    title: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    release_date: str | None = None


@router.patch("/{media_id}")
async def update_media_item(
    session: DBSession,
    media_id: int,
    body: MediaUpdateBody,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update visual metadata for a media item (per-user override)."""
    query = select(MediaItem).where(MediaItem.id == media_id)
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    override = await upsert_media_override(
        session,
        current_user,
        media_id,
        poster_path=body.poster_path,
        backdrop_path=body.backdrop_path,
    )

    logger.info(f"User {current_user.id} updated media override for {media_id}")

    return {
        "id": item.id,
        "title": item.title,
        "overview": item.overview,
        "poster_path": override.poster_path or item.poster_path,
        "backdrop_path": override.backdrop_path or item.backdrop_path,
        "release_date": str(item.release_date) if item.release_date else None,
    }


@router.get("/{media_id}/tmdb-images")
async def get_media_tmdb_images(session: DBSession, media_id: int) -> dict:
    """Fetch available images from TMDB for a media item."""
    query = select(MediaItem).where(MediaItem.id == media_id)
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    if not item.tmdb_id:
        return {"stills": [], "posters": [], "backdrops": []}

    if item.media_type == MediaType.EPISODE and item.series_id:
        # For episodes: fetch stills from TMDB
        from app.models.media import Series
        series_query = select(Series).where(Series.id == item.series_id)
        series_result = await session.execute(series_query)
        series = series_result.scalar_one_or_none()

        if series and series.tmdb_id:
            stills = await tmdb_client.get_episode_images(
                series.tmdb_id,
                item.season_number or 1,
                item.episode_number or 1,
            )
            return {"stills": stills, "posters": [], "backdrops": []}

    # For movies: fetch posters and backdrops
    # Reuse TV images method structure for movies
    params = {"api_key": tmdb_client._api_key}
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.themoviedb.org/3/movie/{item.tmdb_id}/images",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "stills": [],
                "posters": [
                    {"file_path": img["file_path"], "width": img.get("width"), "height": img.get("height")}
                    for img in data.get("posters", [])
                ],
                "backdrops": [
                    {"file_path": img["file_path"], "width": img.get("width"), "height": img.get("height")}
                    for img in data.get("backdrops", [])
                ],
            }
        except httpx.HTTPError:
            return {"stills": [], "posters": [], "backdrops": []}


@router.get("/{media_id}/episodes")
async def get_media_episodes(session: DBSession, media_id: int) -> list[dict]:
    """Get episodes for a TV season from TMDB."""
    query = select(MediaItem).where(MediaItem.id == media_id)
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    if not item.tmdb_id or item.media_type != MediaType.EPISODE:
        return []

    season = item.season_number if item.season_number is not None else 1
    episodes = await tmdb_client.get_season_episodes(item.tmdb_id, season)

    return [
        {
            "episode_number": ep.episode_number,
            "name": ep.name,
            "overview": ep.overview,
            "still_path": ep.still_path,
            "air_date": ep.air_date,
            "runtime": ep.runtime,
        }
        for ep in episodes
    ]
