"""Authentication API endpoints."""

from datetime import UTC, datetime

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from sqlalchemy import delete, select

from app.api.deps import DBSession, get_admin_user, get_current_user
from app.config import get_settings
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

# The admin toggle lives in Redis (like the scheduler intervals) so it survives restarts;
# ENABLE_REGISTRATION is only the default.
REDIS_KEY_REGISTRATION = "tlex:auth:registration_enabled"
_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(get_settings().redis_url)
    return _redis


async def _registration_enabled() -> bool:
    try:
        value = await _get_redis().get(REDIS_KEY_REGISTRATION)
    except Exception as e:
        logger.warning(f"Failed to read registration toggle from Redis: {e}")
        value = None
    return get_settings().enable_registration if value is None else value == b"1"


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
    """Register a new user. The first account is always allowed and becomes admin."""
    is_first_user = (await session.execute(select(User.id).limit(1))).first() is None
    if not is_first_user and not await _registration_enabled():
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
        is_admin=is_first_user,  # otherwise a fresh install has no one who can add workers
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
    # FOR UPDATE: two parallel refreshes with one token must not both succeed
    stmt = select(RefreshToken).where(RefreshToken.token == body.refresh_token).with_for_update()
    result = await session.execute(stmt)
    refresh_token = result.scalar_one_or_none()
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    if refresh_token and refresh_token.revoked:
        # A rotated-out token came back: it was copied. End every session of that user.
        await session.execute(delete(RefreshToken).where(RefreshToken.user_id == refresh_token.user_id))
        await session.commit()
        logger.warning(f"Refresh token reuse for user {refresh_token.user_id}: all sessions revoked")
        raise invalid
    if not refresh_token or refresh_token.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
        raise invalid

    # Get user
    user_stmt = select(User).where(User.id == refresh_token.user_id)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Revoke old refresh token (rotation). Revoked rows stay until they expire so reuse
    # can be detected; expired ones are purged here so the table doesn't grow forever.
    refresh_token.revoked = True
    await session.execute(
        delete(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.expires_at < datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )

    # Create new tokens
    logger.info(f"Token refreshed for: {user.email}")
    return await _create_tokens(session, user)


@router.post("/logout")
async def logout(
    session: DBSession,
    body: RefreshRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Logout: revoke this device's refresh token, or all of the user's without one."""
    stmt = delete(RefreshToken).where(RefreshToken.user_id == current_user.id)
    if body:
        stmt = stmt.where(RefreshToken.token == body.refresh_token)
    await session.execute(stmt)
    await session.commit()

    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Logged out successfully"}


@router.put("/change-password", response_model=TokenResponse)
async def change_password(
    body: ChangePassword,
    session: DBSession,
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    """Change current user's password, end its other sessions, return fresh tokens."""
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
    # A stolen refresh token must stop working once the password changes
    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == current_user.id))

    logger.info(f"Password changed for: {current_user.email}")
    return await _create_tokens(session, current_user)


@router.get("/registration-status")
async def get_registration_status(
    _admin=Depends(get_admin_user),
) -> dict:
    """Get whether registration is open or closed (admin only)."""
    return {"enabled": await _registration_enabled()}


@router.put("/registration-status")
async def set_registration_status(
    body: dict,
    _admin=Depends(get_admin_user),
) -> dict:
    """Toggle registration open/closed (admin only, persisted in Redis)."""
    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="'enabled' must be a boolean")

    try:
        await _get_redis().set(REDIS_KEY_REGISTRATION, "1" if enabled else "0")
    except Exception as e:
        logger.error(f"Failed to save registration toggle: {e}")
        raise HTTPException(status_code=503, detail="Could not save the setting") from None
    logger.info(f"Registration {'enabled' if enabled else 'disabled'} by admin")
    return {"enabled": enabled}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Get current user info."""
    return current_user


@router.get("/users")
async def list_users(
    session: DBSession,
    _admin=Depends(get_admin_user),
) -> list[dict]:
    """List all registered users (admin only)."""
    from sqlalchemy.orm import selectinload

    query = select(User).options(selectinload(User.profiles)).order_by(User.id)
    result = await session.execute(query)
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "is_admin": u.is_admin,
            "profiles_count": len(u.profiles),
            "profiles": [{"id": p.id, "name": p.name} for p in u.profiles],
        }
        for u in users
    ]


@router.patch("/users/{user_id}/admin")
async def toggle_user_admin(
    user_id: int,
    body: dict,
    session: DBSession,
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Toggle admin status for a user (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own admin status")

    target_query = select(User).where(User.id == user_id)
    target_result = await session.execute(target_query)
    target = target_result.scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    is_admin = body.get("is_admin")
    if not isinstance(is_admin, bool):
        raise HTTPException(status_code=400, detail="'is_admin' must be a boolean")

    target.is_admin = is_admin
    await session.commit()

    logger.info(f"User {target.email} admin status set to {is_admin} by {current_user.email}")
    return {"id": target.id, "email": target.email, "is_admin": target.is_admin}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    session: DBSession,
    current_user: User = Depends(get_admin_user),
) -> dict:
    """Delete a user account (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    target_query = select(User).where(User.id == user_id)
    target_result = await session.execute(target_query)
    target = target_result.scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    email = target.email
    await session.delete(target)
    await session.commit()

    logger.info(f"User {email} deleted by {current_user.email}")
    return {"message": f"User {email} deleted"}
