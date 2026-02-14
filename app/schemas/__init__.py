"""Pydantic schemas for API request/response models."""

from app.schemas.auth import ChangePassword, RefreshRequest, TokenResponse, UserCreate, UserResponse
from app.schemas.media import (
    MediaItemDetailResponse,
    MediaItemResponse,
    MediaListResponse,
    MediaPartResponse,
    MediaStreamResponse,
)
from app.schemas.profile import (
    ProfileCreate,
    ProfileListResponse,
    ProfileResponse,
    ProfileUpdate,
)
from app.schemas.scanner import ScanRequest, ScanResponse, ScanStatusResponse
from app.schemas.watchlist import (
    WatchlistItemResponse,
    WatchlistListResponse,
    WatchlistMediaResponse,
)

__all__ = [
    # Auth
    "UserCreate",
    "UserResponse",
    "TokenResponse",
    "RefreshRequest",
    "ChangePassword",
    # Media
    "MediaPartResponse",
    "MediaStreamResponse",
    "MediaItemResponse",
    "MediaItemDetailResponse",
    "MediaListResponse",
    # Profile
    "ProfileCreate",
    "ProfileUpdate",
    "ProfileResponse",
    "ProfileListResponse",
    # Scanner
    "ScanRequest",
    "ScanResponse",
    "ScanStatusResponse",
    # Watchlist
    "WatchlistItemResponse",
    "WatchlistMediaResponse",
    "WatchlistListResponse",
]
