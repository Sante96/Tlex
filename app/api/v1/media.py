"""Media library API endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, get_admin_user
from app.core.worker_manager import worker_manager
from app.models.media import MediaItem, MediaStream, MediaType
from app.schemas import (
    MediaItemDetailResponse,
    MediaItemResponse,
    MediaListResponse,
    MediaPartResponse,
    MediaStreamResponse,
)
from app.services.ffprobe import ffprobe_service
from app.services.tmdb import tmdb_client

router = APIRouter()


@router.get("/", response_model=MediaListResponse)
async def list_media(
    session: DBSession,
    page: int = 1,
    page_size: int = 20,
    media_type: MediaType | None = None,
) -> MediaListResponse:
    """List all media items with pagination."""
    offset = (page - 1) * page_size

    # Base query
    query = select(MediaItem).options(selectinload(MediaItem.parts))

    if media_type:
        query = query.where(MediaItem.media_type == media_type)

    # Get total count
    count_query = select(func.count()).select_from(MediaItem)
    if media_type:
        count_query = count_query.where(MediaItem.media_type == media_type)
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get items
    query = query.offset(offset).limit(page_size).order_by(MediaItem.title)
    result = await session.execute(query)
    items = result.scalars().all()

    return MediaListResponse(
        items=[
            MediaItemResponse(
                id=item.id,
                tmdb_id=item.tmdb_id,
                title=item.title,
                overview=item.overview,
                poster_path=item.poster_path,
                backdrop_path=item.backdrop_path,
                release_date=str(item.release_date) if item.release_date else None,
                media_type=item.media_type.value,
                duration_seconds=item.duration_seconds,
                season_number=item.season_number,
                episode_number=item.episode_number,
                total_size=item.total_size,
                parts_count=len(item.parts),
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{media_id}", response_model=MediaItemDetailResponse)
async def get_media(session: DBSession, media_id: int) -> MediaItemDetailResponse:
    """Get detailed media item by ID."""
    query = (
        select(MediaItem)
        .where(MediaItem.id == media_id)
        .options(selectinload(MediaItem.parts), selectinload(MediaItem.streams))
    )
    result = await session.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Media not found")

    return MediaItemDetailResponse(
        id=item.id,
        tmdb_id=item.tmdb_id,
        title=item.title,
        overview=item.overview,
        poster_path=item.poster_path,
        backdrop_path=item.backdrop_path,
        release_date=str(item.release_date) if item.release_date else None,
        media_type=item.media_type.value,
        duration_seconds=item.duration_seconds,
        season_number=item.season_number,
        episode_number=item.episode_number,
        total_size=item.total_size,
        parts_count=len(item.parts),
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

    # Search TMDB based on media type
    if item.media_type == MediaType.MOVIE:
        tmdb_result = await tmdb_client.search_movie(item.title)
    else:
        tmdb_result = await tmdb_client.search_tv(
            item.title, item.season_number, item.episode_number
        )

    if not tmdb_result:
        raise HTTPException(
            status_code=404,
            detail=f"No TMDB results found for: {item.title}"
        )

    # Update metadata
    old_title = item.title
    item.tmdb_id = tmdb_result.tmdb_id
    item.title = tmdb_result.title
    item.overview = tmdb_result.overview
    item.poster_path = tmdb_result.poster_path
    item.backdrop_path = tmdb_result.backdrop_path

    if tmdb_result.release_date:
        try:
            item.release_date = date.fromisoformat(tmdb_result.release_date)
        except ValueError:
            pass  # Invalid date format, skip

    await session.commit()

    logger.info(f"Refreshed metadata: '{old_title}' -> '{item.title}'")

    return {
        "message": f"Metadata refreshed for: {item.title}",
        "tmdb_id": tmdb_result.tmdb_id,
        "title": tmdb_result.title,
        "poster_path": tmdb_result.poster_path,
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
