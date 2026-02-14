"""Authentication API endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from sqlalchemy import delete, select

from app.api.deps import DBSession, get_admin_user, get_current_user
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    get_refresh_token_expiry,
    hash_password,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas import ChangePassword, RefreshRequest, TokenResponse, UserCreate, UserResponse

router = APIRouter()


async def _create_tokens(session: DBSession, user: User) -> TokenResponse:
    """Create access and refresh tokens for a user."""
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_value = generate_refresh_token()

    refresh_token = RefreshToken(
        user_id=user.id,
        token=refresh_token_value,
        expires_at=get_refresh_token_expiry(),
    )
    session.add(refresh_token)
    await session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_LIMIT)
async def register(request: Request, user_data: UserCreate, session: DBSession) -> User:
    """Register a new user."""
    from app.config import get_settings

    if not get_settings().enable_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled",
        )

    stmt = select(User).where(User.email == user_data.email)
    result = await session.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        is_admin=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info(f"New user registered: {user.email}")
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_LIMIT)
async def login(
    request: Request,
    session: DBSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """Login and get access + refresh tokens."""
    stmt = select(User).where(User.email == form_data.username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"User logged in: {user.email}")
    return await _create_tokens(session, user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(AUTH_LIMIT)
async def refresh_tokens(request: Request, body: RefreshRequest, session: DBSession) -> TokenResponse:
    """Refresh access token using refresh token."""
    stmt = select(RefreshToken).where(
        RefreshToken.token == body.refresh_token,
        RefreshToken.revoked == False,  # noqa: E712
        RefreshToken.expires_at > datetime.now(UTC),
    )
    result = await session.execute(stmt)
    refresh_token = result.scalar_one_or_none()

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Get user
    user_stmt = select(User).where(User.id == refresh_token.user_id)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Revoke old refresh token (rotation)
    refresh_token.revoked = True

    # Create new tokens
    logger.info(f"Token refreshed for: {user.email}")
    return await _create_tokens(session, user)


@router.post("/logout")
async def logout(
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Logout and revoke all refresh tokens for the user."""
    stmt = (
        delete(RefreshToken)
        .where(RefreshToken.user_id == current_user.id)
    )
    await session.execute(stmt)
    await session.commit()

    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Logged out successfully"}


@router.put("/change-password")
async def change_password(
    body: ChangePassword,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Change current user's password."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters",
        )

    current_user.password_hash = hash_password(body.new_password)
    await session.commit()

    logger.info(f"Password changed for: {current_user.email}")
    return {"message": "Password changed successfully"}


@router.get("/registration-status")
async def get_registration_status(
    _admin=Depends(get_admin_user),
) -> dict:
    """Get whether registration is open or closed (admin only)."""
    from app.config import get_settings
    return {"enabled": get_settings().enable_registration}


@router.put("/registration-status")
async def set_registration_status(
    body: dict,
    _admin=Depends(get_admin_user),
) -> dict:
    """Toggle registration open/closed at runtime (admin only)."""
    from app.config import get_settings

    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="'enabled' must be a boolean")

    get_settings().enable_registration = enabled
    logger.info(f"Registration {'enabled' if enabled else 'disabled'} by admin")
    return {"enabled": enabled}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Get current user info."""
    return current_user
