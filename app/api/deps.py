"""Dependency injection for API routes."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
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

    stmt = select(User).where(User.id == int(user_id))
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


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

    stmt = select(User).where(User.id == int(user_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


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
