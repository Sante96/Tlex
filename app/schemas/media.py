"""Media schemas."""

from pydantic import BaseModel


class MediaPartResponse(BaseModel):
    """Response model for media part."""

    id: int
    part_index: int
    file_size: int

    class Config:
        from_attributes = True


class MediaStreamResponse(BaseModel):
    """Response model for media stream."""

    id: int
    stream_index: int
    codec_type: str
    codec_name: str
    language: str | None
    title: str | None
    is_default: bool

    class Config:
        from_attributes = True


class MediaItemResponse(BaseModel):
    """Response model for media item."""

    id: int
    tmdb_id: int | None
    title: str
    overview: str | None
    poster_path: str | None
    backdrop_path: str | None
    release_date: str | None
    media_type: str
    duration_seconds: int | None
    season_number: int | None
    episode_number: int | None
    total_size: int
    parts_count: int
    vote_average: float | None = None
    genres: list[str] | None = None

    class Config:
        from_attributes = True


class MediaItemDetailResponse(MediaItemResponse):
    """Detailed response with parts and streams."""

    parts: list[MediaPartResponse]
    streams: list[MediaStreamResponse]


class MediaListResponse(BaseModel):
    """Response model for media list."""

    items: list[MediaItemResponse]
    total: int
    page: int
    page_size: int
