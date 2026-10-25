"""Dependency injection for API routes."""

import secrets
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Dependency for database session."""
    async with async_session_maker() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]

# Optional: the browser's session is the httpOnly `token` cookie; the header serves API
# clients (and the docs' Authorize button)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    session: DBSession,
    token: str | None = Depends(oauth2_scheme_optional),
):
    """Get the current authenticated user from the JWT: Authorization header or cookie."""
    from app.core.security import decode_access_token
    from app.models.user import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = token or request.cookies.get("token")
    payload = decode_access_token(token) if token else None
    if payload is None:
        raise credentials_exception

    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # get, not a SELECT: routers and endpoints both resolve the user on the same request's
    # session, and the second lookup comes from its identity map
    user = await session.get(User, int(user_id))

    if user is None:
        raise credentials_exception

    return user


async def get_stream_user(
    request: Request,
    session: DBSession,
    token: str | None = Depends(oauth2_scheme_optional),
):
    """get_current_user for stream/subtitle routes, which also take the internal token
    ffmpeg uses to read /stream/raw. <video> and the libass worker send the cookie.
    """
    from app.core.security import INTERNAL_STREAM_TOKEN

    internal = request.query_params.get("internal", "")
    if internal and secrets.compare_digest(internal, INTERNAL_STREAM_TOKEN):
        return None
    return await get_current_user(request, session, token)


async def get_current_user_optional(
    request: Request,
    session: DBSession,
    token: str | None = Depends(oauth2_scheme_optional),
):
    """Get the current user if authenticated, otherwise return None."""
    token = token or request.cookies.get("token")
    if not token:
        return None

    from app.core.security import decode_access_token
    from app.models.user import User

    payload = decode_access_token(token)
    if payload is None:
        return None

    user_id: int | None = payload.get("sub")
    if user_id is None:
        return None

    return await session.get(User, int(user_id))


async def get_admin_user(
    current_user=Depends(get_current_user),
):
    """Require admin user for protected endpoints."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# The profile picked on this device: the frontend keeps its id in this cookie
PROFILE_COOKIE = "selected_profile_id"


async def get_current_profile(
    request: Request,
    session: DBSession,
    current_user=Depends(get_current_user),
):
    """The profile watching: watch progress and the watchlist belong to it.

    The one picked on this device, if it is the user's; otherwise the user's first.
    Every user has one (registration creates it, the last one can't be deleted).
    """
    from sqlalchemy import select

    from app.models.user import Profile

    profiles = (
        (
            await session.execute(
                select(Profile).where(Profile.user_id == current_user.id).order_by(Profile.id)
            )
        )
        .scalars()
        .all()
    )
    if not profiles:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No profile")
    wanted = request.cookies.get(PROFILE_COOKIE)
    return next((p for p in profiles if str(p.id) == wanted), profiles[0])
