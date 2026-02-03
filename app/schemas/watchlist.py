"""Watchlist/Favorites schemas."""

from datetime import datetime

from pydantic import BaseModel


class WatchlistItemResponse(BaseModel):
    """Response model for a watchlist item."""

    id: int
    media_item_id: int
    added_at: datetime

    class Config:
        from_attributes = True


class WatchlistMediaResponse(BaseModel):
    """Response model for watchlist with media details."""

    id: int
    media_item_id: int
    added_at: datetime
    title: str
    poster_path: str | None
    media_type: str
    duration_seconds: int | None

    class Config:
        from_attributes = True


class WatchlistListResponse(BaseModel):
    """Response model for watchlist list."""

    items: list[WatchlistMediaResponse]
    total: int
