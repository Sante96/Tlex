"""Profile schemas."""

from pydantic import BaseModel


class ProfileCreate(BaseModel):
    """Request model for profile creation."""

    name: str
    avatar_url: str | None = None
    is_kids: bool = False


class ProfileUpdate(BaseModel):
    """Request model for profile update."""

    name: str | None = None
    avatar_url: str | None = None
    is_kids: bool | None = None
    preferences: dict | None = None


class ProfileResponse(BaseModel):
    """Response model for profile data."""

    id: int
    user_id: int
    worker_id: int | None
    name: str
    avatar_url: str | None
    is_kids: bool
    preferences: dict
    has_worker: bool = False

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_worker(cls, profile) -> "ProfileResponse":
        """Create response with worker availability check."""
        return cls(
            id=profile.id,
            user_id=profile.user_id,
            worker_id=profile.worker_id,
            name=profile.name,
            avatar_url=profile.avatar_url,
            is_kids=profile.is_kids,
            preferences=profile.preferences,
            has_worker=profile.worker_id is not None,
        )


class ProfileListResponse(BaseModel):
    """Response model for list of profiles."""

    profiles: list[ProfileResponse]
    has_profiles: bool
