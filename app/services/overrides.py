"""Per-user metadata override helpers.

Each user can customize visual metadata (poster, backdrop) for media items
and series. Base data comes from TMDB; overrides are layered on top per-user.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserMediaOverride, UserSeriesOverride


async def get_media_overrides(
    session: AsyncSession,
    user: User,
    media_ids: list[int],
) -> dict[int, UserMediaOverride]:
    """Fetch user overrides for a batch of media items."""
    if not media_ids:
        return {}

    query = select(UserMediaOverride).where(
        UserMediaOverride.user_id == user.id,
        UserMediaOverride.media_item_id.in_(media_ids),
    )
    result = await session.execute(query)
    return {o.media_item_id: o for o in result.scalars().all()}


async def get_media_override(
    session: AsyncSession,
    user: User,
    media_id: int,
) -> UserMediaOverride | None:
    """Fetch user override for a single media item."""
    query = select(UserMediaOverride).where(
        UserMediaOverride.user_id == user.id,
        UserMediaOverride.media_item_id == media_id,
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_series_override(
    session: AsyncSession,
    user: User,
    series_id: int,
) -> UserSeriesOverride | None:
    """Fetch user override for a single series."""
    query = select(UserSeriesOverride).where(
        UserSeriesOverride.user_id == user.id,
        UserSeriesOverride.series_id == series_id,
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_series_overrides(
    session: AsyncSession,
    user: User,
    series_ids: list[int],
) -> dict[int, UserSeriesOverride]:
    """Fetch user overrides for a batch of series."""
    if not series_ids:
        return {}

    query = select(UserSeriesOverride).where(
        UserSeriesOverride.user_id == user.id,
        UserSeriesOverride.series_id.in_(series_ids),
    )
    result = await session.execute(query)
    return {o.series_id: o for o in result.scalars().all()}


def apply_media_override(
    data: dict,
    override: UserMediaOverride | None,
) -> dict:
    """Merge user override fields on top of base media data."""
    if not override:
        return data

    if override.poster_path is not None:
        data["poster_path"] = override.poster_path
    if override.backdrop_path is not None:
        data["backdrop_path"] = override.backdrop_path

    return data


def apply_series_override(
    data: dict,
    override: UserSeriesOverride | None,
) -> dict:
    """Merge user override fields on top of base series data."""
    if not override:
        return data

    if override.poster_path is not None:
        data["poster_path"] = override.poster_path
    if override.backdrop_path is not None:
        data["backdrop_path"] = override.backdrop_path

    return data


async def upsert_media_override(
    session: AsyncSession,
    user: User,
    media_id: int,
    poster_path: str | None = None,
    backdrop_path: str | None = None,
) -> UserMediaOverride:
    """Create or update a per-user media override."""
    override = await get_media_override(session, user, media_id)

    if not override:
        override = UserMediaOverride(user_id=user.id, media_item_id=media_id)
        session.add(override)

    if poster_path is not None:
        override.poster_path = poster_path
    if backdrop_path is not None:
        override.backdrop_path = backdrop_path

    await session.commit()
    return override


async def upsert_series_override(
    session: AsyncSession,
    user: User,
    series_id: int,
    poster_path: str | None = None,
    backdrop_path: str | None = None,
    season_posters: dict | None = None,
) -> UserSeriesOverride:
    """Create or update a per-user series override."""
    override = await get_series_override(session, user, series_id)

    if not override:
        override = UserSeriesOverride(user_id=user.id, series_id=series_id)
        session.add(override)

    if poster_path is not None:
        override.poster_path = poster_path
    if backdrop_path is not None:
        override.backdrop_path = backdrop_path
    if season_posters is not None:
        override.season_posters = season_posters

    await session.commit()
    return override
