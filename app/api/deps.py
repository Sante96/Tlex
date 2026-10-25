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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    session: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """Get the current authenticated user from JWT token."""
    from app.core.security import decode_access_token
    from app.models.user import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
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
    """get_current_user for stream/subtitle routes.

    Also accepts the `token` cookie, since <video> and the libass worker can't send an
    Authorization header, and the internal token ffmpeg uses to read /stream/raw.
    """
    from app.core.security import INTERNAL_STREAM_TOKEN

    internal = request.query_params.get("internal", "")
    if internal and secrets.compare_digest(internal, INTERNAL_STREAM_TOKEN):
        return None
    return await get_current_user(session, token or request.cookies.get("token") or "")


async def get_current_user_optional(
    session: DBSession,
    token: str | None = Depends(oauth2_scheme_optional),
):
    """Get the current user if authenticated, otherwise return None."""
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
