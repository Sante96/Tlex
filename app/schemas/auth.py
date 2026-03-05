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


class ChangePassword(BaseModel):
    """Request model for password change."""

    current_password: str
    new_password: str


class DeviceCodeResponse(BaseModel):
    """Response when a TV requests a device code."""

    user_code: str
    device_code: str
    expires_in: int
    interval: int = 5


class DeviceConfirmRequest(BaseModel):
    """Request from browser to confirm a device code."""

    user_code: str
    email: EmailStr
    password: str


class DevicePollResponse(BaseModel):
    """Response when TV polls for auth status."""

    status: str  # "pending" | "confirmed" | "expired"
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
