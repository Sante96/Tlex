"""Watchlist/Favorites schemas."""

from datetime import datetime

from pydantic import BaseModel


class WatchlistItemResponse(BaseModel):
    """Response model for a watchlist item."""

    id: int
    media_item_id: int | None = None
    series_id: int | None = None
    added_at: datetime

    class Config:
        from_attributes = True


class WatchlistMediaResponse(BaseModel):
    """Response model for watchlist with media details."""

    id: int
    media_item_id: int | None = None
    series_id: int | None = None
    item_type: str  # "movie", "episode", or "series"
    added_at: datetime
    title: str
    poster_path: str | None
    media_type: str | None = None
    duration_seconds: int | None = None

    class Config:
        from_attributes = True


class WatchlistListResponse(BaseModel):
    """Response model for watchlist list."""

    items: list[WatchlistMediaResponse]
    total: int
