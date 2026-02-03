"""Authentication schemas."""

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Request model for user registration."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response model for user data."""

    id: int
    email: str
    is_admin: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response model for authentication token."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request model for token refresh."""

    refresh_token: str
