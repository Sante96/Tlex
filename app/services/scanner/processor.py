"""Media processing logic for scanner."""

from datetime import date

from guessit import guessit
from loguru import logger
from pyrogram import Client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaPart, MediaStream, MediaType, Series
from app.services.ffprobe import ffprobe_service
from app.services.scanner.models import MediaGroup, ScannedFile
from app.services.tmdb import tmdb_client


async def process_group(
    session: AsyncSession,
    group: MediaGroup,
    client: Client | None = None,
    force_movie: bool = False,
    series_name: str | None = None,
) -> MediaItem | None:
    """Process a media group and create database entries."""
    first_file = group.files[0]
    existing_part = await session.execute(
        select(MediaPart).where(
            MediaPart.channel_id == first_file.channel_id,
            MediaPart.message_id == first_file.message_id,
        )
    )
    if existing_part.scalar_one_or_none():
        logger.debug(f"Skipping existing: {group.base_name}")
        return None

    guess = guessit(group.base_name)
    title = guess.get("title", group.base_name)
    year = guess.get("year")

    season = guess.get("season")
    episode = guess.get("episode")

    # Detect OVA/Special
    other_tags = guess.get("other", [])
    if isinstance(other_tags, str):
        other_tags = [other_tags]
    is_special = any(
        tag in other_tags for tag in ["Original Animated Video", "Original Net Animation"]
    )
    alt_title = guess.get("alternative_title", "")
    if isinstance(alt_title, str) and alt_title.lower() == "special":
        is_special = True

    if is_special and season is None:
        season = 0
        if episode is None:
            episode = 1

    # Determine media type
    if force_movie:
        media_type = MediaType.MOVIE
    elif series_name:
        media_type = MediaType.EPISODE
        title = series_name
        if season is None and episode is None:
            season = 0
            episode = 1
        elif season is None and episode is not None:
            season = 1
    elif season is not None or episode is not None:
        media_type = MediaType.EPISODE
        if season is None and episode is not None:
            season = 1
    else:
        media_type = MediaType.MOVIE

    # Fetch TMDB metadata
    tmdb_result = None
    series_obj = None

    if media_type == MediaType.MOVIE:
        tmdb_result = await tmdb_client.search_movie(title, year)
    else:
        tmdb_result = await tmdb_client.search_tv(title, season, episode)

        if tmdb_result:
            series_query = select(Series).where(Series.tmdb_id == tmdb_result.tmdb_id)
            series_result = await session.execute(series_query)
            series_obj = series_result.scalar_one_or_none()

            if not series_obj:
                # Fetch detailed info (genres, rating, content_rating)
                tv_details = await tmdb_client.get_tv_details(tmdb_result.tmdb_id)

                series_obj = Series(
                    tmdb_id=tmdb_result.tmdb_id,
                    title=tmdb_result.title,
                    overview=tmdb_result.overview,
                    poster_path=tmdb_result.poster_path,
                    backdrop_path=tmdb_result.backdrop_path,
                    first_air_date=(
                        date.fromisoformat(tmdb_result.release_date)
                        if tmdb_result.release_date
                        else None
                    ),
                    genres=",".join(tv_details.genres) if tv_details and tv_details.genres else None,
                    vote_average=tv_details.vote_average if tv_details else None,
                    content_rating=tv_details.content_rating if tv_details else None,
                )
                session.add(series_obj)
                await session.flush()
                logger.debug(f"Created series: {series_obj.title}")

    # Get episode details
    episode_title = tmdb_result.title if tmdb_result else title
    episode_overview = tmdb_result.overview if tmdb_result else None
    episode_still = None

    if media_type == MediaType.EPISODE and tmdb_result and season is not None and episode:
        ep_details = await tmdb_client.get_episode_details(tmdb_result.tmdb_id, season, episode)
        if ep_details:
            ep_name = ep_details.name
            if season == 0 and (
                not ep_name
                or ep_name.lower().startswith("episodio")
                or ep_name.lower().startswith("episode")
            ):
                ep_name = group.base_name.rsplit(".", 1)[0]
            episode_title = f"S{season:02d}E{episode:02d} - {ep_name}"
            episode_overview = ep_details.overview or tmdb_result.overview
            episode_still = ep_details.still_path
        elif season == 0:
            ep_name = group.base_name.rsplit(".", 1)[0]
            episode_title = f"S00E{episode:02d} - {ep_name}"

    # Create MediaItem
    media_item = MediaItem(
        title=episode_title,
        tmdb_id=tmdb_result.tmdb_id if tmdb_result else None,
        overview=episode_overview,
        poster_path=episode_still or (tmdb_result.poster_path if tmdb_result else None),
        backdrop_path=tmdb_result.backdrop_path if tmdb_result else None,
        release_date=(
            date.fromisoformat(tmdb_result.release_date)
            if tmdb_result and tmdb_result.release_date
            else None
        ),
        media_type=media_type,
        series_id=series_obj.id if series_obj else None,
        season_number=season,
        episode_number=episode,
    )

    session.add(media_item)
    await session.flush()

    # Create MediaParts
    current_offset = 0
    for idx, f in enumerate(group.files):
        part = MediaPart(
            media_item_id=media_item.id,
            telegram_file_id=f.file_id,
            part_index=idx,
            start_byte=current_offset,
            end_byte=current_offset + f.file_size,
            file_size=f.file_size,
            channel_id=f.channel_id,
            topic_id=f.topic_id,
            message_id=f.message_id,
        )
        session.add(part)
        current_offset += f.file_size

    # Analyze streams
    if client and group.files:
        await analyze_streams(session, media_item, group.files[0], client)

    await session.commit()
    logger.debug(f"Created: {media_item.title} ({len(group.files)} parts)")

    return media_item


async def analyze_streams(
    session: AsyncSession,
    media_item: MediaItem,
    first_file: ScannedFile,
    client: Client,
) -> None:
    """Analyze media streams using ffprobe."""
    try:
        logger.debug(f"Analyzing streams for: {media_item.title}")

        probe_result = await ffprobe_service.analyze_from_telegram(client, first_file.file_id)

        if probe_result:
            if probe_result.duration_seconds:
                media_item.duration_seconds = probe_result.duration_seconds

            has_subtitles = False
            for stream_info in probe_result.streams:
                stream = MediaStream(
                    media_item_id=media_item.id,
                    stream_index=stream_info.stream_index,
                    codec_type=stream_info.codec_type,
                    codec_name=stream_info.codec_name,
                    language=stream_info.language,
                    title=stream_info.title,
                    is_default=stream_info.is_default,
                )
                session.add(stream)
                if stream_info.codec_type.value == "subtitle":
                    has_subtitles = True

            logger.debug(f"Found {len(probe_result.streams)} streams")

            # Pre-extract fonts/subtitles in background if media has subtitles
            if has_subtitles:
                import asyncio

                from app.database import async_session_maker
                from app.services.subtitles.cache import ensure_cache_populated

                async def extract_in_background():
                    try:
                        # Wait a bit for commit to complete
                        await asyncio.sleep(2)
                        async with async_session_maker() as bg_session:
                            await ensure_cache_populated(media_item.id, bg_session)
                    except Exception as e:
                        logger.warning(f"Background cache extraction failed: {e}")

                asyncio.create_task(extract_in_background())
                logger.debug(f"Queued background subtitle cache extraction for: {media_item.title}")

    except Exception as e:
        logger.error(f"Failed to analyze streams: {e}")
