"""Watchlist/Favorites API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DBSession, get_current_user
from app.models.media import MediaItem
from app.models.user import User, Watchlist
from app.schemas import WatchlistListResponse, WatchlistMediaResponse

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistListResponse)
async def get_watchlist(
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> WatchlistListResponse:
    """Get current user's watchlist with media details."""
    query = (
        select(Watchlist, MediaItem)
        .join(MediaItem, Watchlist.media_item_id == MediaItem.id)
        .where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc())
    )
    result = await session.execute(query)
    rows = result.all()

    items = [
        WatchlistMediaResponse(
            id=watchlist.id,
            media_item_id=watchlist.media_item_id,
            added_at=watchlist.added_at,
            title=media.title,
            poster_path=media.poster_path,
            media_type=media.media_type.value,
            duration_seconds=media.duration_seconds,
        )
        for watchlist, media in rows
    ]

    return WatchlistListResponse(items=items, total=len(items))


@router.post("/{media_id}", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    media_id: int,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Add a media item to the user's watchlist."""
    # Check if media exists
    media_query = select(MediaItem).where(MediaItem.id == media_id)
    media_result = await session.execute(media_query)
    media = media_result.scalar_one_or_none()

    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    # Check if already in watchlist
    existing_query = select(Watchlist).where(
        Watchlist.user_id == current_user.id,
        Watchlist.media_item_id == media_id,
    )
    existing_result = await session.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Already in watchlist")

    # Add to watchlist
    watchlist_item = Watchlist(
        user_id=current_user.id,
        media_item_id=media_id,
    )
    session.add(watchlist_item)
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
    watchlist_item = result.scalar_one_or_none()

    return {"in_watchlist": watchlist_item is not None}
