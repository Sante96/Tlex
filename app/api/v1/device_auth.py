"""Device authorization endpoints for TV / set-top-box login flow."""

import random
import secrets
import string
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import delete, select

from app.api.deps import DBSession
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.core.security import create_access_token, generate_refresh_token, get_refresh_token_expiry, verify_password
from app.models.user import DeviceCode, RefreshToken, User
from app.schemas.auth import DeviceCodeResponse, DeviceConfirmRequest, DevicePollResponse

router = APIRouter()

_DEVICE_CODE_TTL_SECONDS = 300  # 5 minutes


def _generate_user_code() -> str:
    """Generate a short human-readable 6-char uppercase code."""
    chars = string.ascii_uppercase.replace("O", "").replace("I", "") + string.digits.replace("0", "")
    return "".join(random.choices(chars, k=6))


@router.post("/device/request", response_model=DeviceCodeResponse)
@limiter.limit(AUTH_LIMIT)
async def device_request(request: Request, session: DBSession) -> DeviceCodeResponse:
    """TV requests a device code to start the login flow."""
    user_code = _generate_user_code()
    device_code = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(seconds=_DEVICE_CODE_TTL_SECONDS)

    # Cleanup expired codes
    await session.execute(
        delete(DeviceCode).where(DeviceCode.expires_at < datetime.now(UTC))
    )

    entry = DeviceCode(
        user_code=user_code,
        device_code=device_code,
        expires_at=expires_at,
    )
    session.add(entry)
    await session.commit()

    return DeviceCodeResponse(
        user_code=user_code,
        device_code=device_code,
        expires_in=_DEVICE_CODE_TTL_SECONDS,
    )


@router.post("/device/confirm")
@limiter.limit(AUTH_LIMIT)
async def device_confirm(
    request: Request,
    body: DeviceConfirmRequest,
    session: DBSession,
) -> dict:
    """Browser submits email + password + user_code to authorize the TV."""
    stmt = select(DeviceCode).where(
        DeviceCode.user_code == body.user_code.upper(),
        DeviceCode.confirmed == False,  # noqa: E712
        DeviceCode.expires_at > datetime.now(UTC),
    )
    result = await session.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired code",
        )

    user_stmt = select(User).where(User.email == body.email)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    entry.confirmed = True
    entry.user_id = user.id
    await session.commit()

    return {"message": "Device authorized successfully"}


@router.get("/device/poll", response_model=DevicePollResponse)
async def device_poll(device_code: str, session: DBSession) -> DevicePollResponse:
    """TV polls to check if the user has confirmed the device code."""
    stmt = select(DeviceCode).where(DeviceCode.device_code == device_code)
    result = await session.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device code not found")

    if entry.expires_at < datetime.now(UTC):
        await session.delete(entry)
        await session.commit()
        return DevicePollResponse(status="expired")

    if not entry.confirmed or entry.user_id is None:
        return DevicePollResponse(status="pending")

    # Confirmed — issue tokens and delete the device code entry
    user_stmt = select(User).where(User.id == entry.user_id)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        return DevicePollResponse(status="pending")

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_value = generate_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        token=refresh_token_value,
        expires_at=get_refresh_token_expiry(),
    )
    session.add(refresh_token)
    await session.delete(entry)
    await session.commit()

    return DevicePollResponse(
        status="confirmed",
        access_token=access_token,
        refresh_token=refresh_token_value,
    )
