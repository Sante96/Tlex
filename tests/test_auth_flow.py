"""Offline checks for the auth hardening: first-user bootstrap, refresh-token rotation and
reuse detection, password change, rate-limit key and the login wall on the catalog."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette.requests import Request

import app.api.v1.auth as auth
from app.core.rate_limit import client_ip, limiter
from app.core.security import hash_password
from app.main import app
from app.models.user import RefreshToken, User
from app.schemas import ChangePassword, RefreshRequest, UserCreate


def _request(headers: dict | None = None) -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("10.0.0.5", 1234),
    })


@pytest.fixture(autouse=True)
def no_rate_limit(monkeypatch):
    monkeypatch.setattr(limiter, "enabled", False)


async def _user(session, email="u@example.com", password="x") -> User:
    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    await session.commit()
    return user


async def test_first_account_registers_as_admin_even_when_closed(test_session, monkeypatch):
    monkeypatch.setattr(auth, "_registration_enabled", AsyncMock(return_value=False))

    first = await auth.register(_request(), UserCreate(email="a@example.com", password="secret1"), test_session)
    assert first.is_admin

    with pytest.raises(HTTPException) as exc:
        await auth.register(_request(), UserCreate(email="b@example.com", password="secret1"), test_session)
    assert exc.value.status_code == 403


async def test_reused_refresh_token_revokes_every_session(test_session):
    user = await _user(test_session)
    tokens = await auth._create_tokens(test_session, user)

    await auth.refresh_tokens(_request(), RefreshRequest(refresh_token=tokens.refresh_token), test_session)
    with pytest.raises(HTTPException) as exc:  # the same (now rotated-out) token again: a copy
        await auth.refresh_tokens(_request(), RefreshRequest(refresh_token=tokens.refresh_token), test_session)

    assert exc.value.status_code == 401
    assert (await test_session.execute(select(RefreshToken))).scalars().all() == []


async def test_change_password_revokes_old_refresh_tokens(test_session):
    user = await _user(test_session, password="oldpass1")
    await auth._create_tokens(test_session, user)

    new = await auth.change_password(
        ChangePassword(current_password="oldpass1", new_password="newpass1"), test_session, user
    )

    tokens = (await test_session.execute(select(RefreshToken.token))).scalars().all()
    assert tokens == [new.refresh_token]


def test_rate_limit_key_uses_real_client_ip():
    assert client_ip(_request({"CF-Connecting-IP": "1.1.1.1", "X-Forwarded-For": "2.2.2.2"})) == "1.1.1.1"
    assert client_ip(_request({"X-Forwarded-For": "3.3.3.3, 172.18.0.5"})) == "3.3.3.3"
    assert client_ip(_request()) == "10.0.0.5"


async def test_catalog_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for path in ("/api/v1/media", "/api/v1/series", "/api/v1/series/1/season/1", "/api/v1/people/1"):
            assert (await c.get(path)).status_code == 401, path
