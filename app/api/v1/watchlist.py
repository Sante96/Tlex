"""Watchlist/Favorites API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DBSession, get_current_user
from app.models.media import MediaItem, Series
from app.models.user import User, Watchlist
from app.schemas import WatchlistListResponse, WatchlistMediaResponse

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistListResponse)
async def get_watchlist(
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> WatchlistListResponse:
    """Get current user's watchlist with media details (movies + series)."""
    query = (
        select(Watchlist)
        .where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc())
    )
    result = await session.execute(query)
    watchlist_rows = result.scalars().all()

    items: list[WatchlistMediaResponse] = []
    for wl in watchlist_rows:
        if wl.media_item_id:
            media_result = await session.execute(
                select(MediaItem).where(MediaItem.id == wl.media_item_id)
            )
            media = media_result.scalar_one_or_none()
            if media:
                items.append(WatchlistMediaResponse(
                    id=wl.id,
                    media_item_id=wl.media_item_id,
                    item_type=media.media_type.value.lower(),
                    added_at=wl.added_at,
                    title=media.title,
                    poster_path=media.poster_path,
                    media_type=media.media_type.value,
                    duration_seconds=media.duration_seconds,
                ))
        elif wl.series_id:
            series_result = await session.execute(
                select(Series).where(Series.id == wl.series_id)
            )
            series = series_result.scalar_one_or_none()
            if series:
                items.append(WatchlistMediaResponse(
                    id=wl.id,
                    series_id=wl.series_id,
                    item_type="series",
                    added_at=wl.added_at,
                    title=series.title,
                    poster_path=series.poster_path,
                ))

    return WatchlistListResponse(items=items, total=len(items))


# ── Media item watchlist ──────────────────────────────────────────


@router.post("/{media_id}", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    media_id: int,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Add a media item to the user's watchlist."""
    media_query = select(MediaItem).where(MediaItem.id == media_id)
    media_result = await session.execute(media_query)
    media = media_result.scalar_one_or_none()

    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    existing_query = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.media_item_id == media_id,
    )
    existing_result = await session.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already in watchlist")

    session.add(Watchlist(user_id=current_user.id, media_item_id=media_id))
    await session.commit()
    return {"message": f"Added '{media.title}' to watchlist"}


@router.delete("/{media_id}")
async def remove_from_watchlist(
    media_id: int,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Remove a media item from the user's watchlist."""
    query = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.media_item_id == media_id,
    )
    result = await session.execute(query)
    watchlist_item = result.scalar_one_or_none()
    if not watchlist_item:
        raise HTTPException(status_code=404, detail="Not in watchlist")

    await session.delete(watchlist_item)
    await session.commit()
    return {"message": "Removed from watchlist"}


@router.get("/{media_id}/status")
async def check_watchlist_status(
    media_id: int,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Check if a media item is in the user's watchlist."""
    query = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.media_item_id == media_id,
    )
    result = await session.execute(query)
    return {"in_watchlist": result.scalar_one_or_none() is not None}


# ── Series watchlist ──────────────────────────────────────────────


@router.post("/series/{series_id}", status_code=status.HTTP_201_CREATED)
async def add_series_to_watchlist(
    series_id: int,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Add a series to the user's watchlist."""
    series_query = select(Series).where(Series.id == series_id)
    series_result = await session.execute(series_query)
    series = series_result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    existing_query = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.series_id == series_id,
    )
    existing_result = await session.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already in watchlist")

    session.add(Watchlist(user_id=current_user.id, series_id=series_id))
    await session.commit()
    return {"message": f"Added '{series.title}' to watchlist"}


@router.delete("/series/{series_id}")
async def remove_series_from_watchlist(
    series_id: int,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Remove a series from the user's watchlist."""
    query = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.series_id == series_id,
    )
    result = await session.execute(query)
    watchlist_item = result.scalar_one_or_none()
    if not watchlist_item:
        raise HTTPException(status_code=404, detail="Not in watchlist")

    await session.delete(watchlist_item)
    await session.commit()
    return {"message": "Removed from watchlist"}


@router.get("/series/{series_id}/status")
async def check_series_watchlist_status(
    series_id: int,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Check if a series is in the user's watchlist."""
    query = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.series_id == series_id,
    )
    result = await session.execute(query)
    return {"in_watchlist": result.scalar_one_or_none() is not None}
