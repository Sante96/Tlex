"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "securepass123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert data["is_admin"] is True  # the first account administers the server

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "second@example.com", "password": "securepass123"},
    )
    assert second.json()["is_admin"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Test registration with duplicate email fails."""
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": "pass123"},
    )
    
    # Second registration with same email
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": "pass456"},
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login."""
    # Register user first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "logintest@example.com", "password": "testpass123"},
    )
    
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "logintest@example.com", "password": "testpass123"},
    )
    assert response.status_code == 200
    # The tokens are httpOnly cookies, not in the body (an XSS could read a body)
    assert set(response.json()) == {"expires_at"}
    cookies = response.headers.get_list("set-cookie")
    for name in ("token", "refresh_token"):
        header = next(c for c in cookies if c.startswith(f"{name}="))
        assert "HttpOnly" in header and "SameSite=lax" in header and "Path=/" in header
    assert "HttpOnly" not in next(c for c in cookies if c.startswith("token_exp="))
    assert int(client.cookies["token_exp"]) == response.json()["expires_at"]
    # Plain HTTP (the LAN address): Secure would make the browser drop them
    assert not any("Secure" in c for c in cookies)

    # The cookie alone authenticates
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "logintest@example.com"


@pytest.mark.asyncio
async def test_session_cookies_are_secure_on_https(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "https@example.com", "password": "testpass123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "https@example.com", "password": "testpass123"},
        headers={"Origin": "https://tlex.example.com"},  # the page, behind the tunnel
    )
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 3 and all("Secure" in c for c in cookies)


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Test login with wrong password fails."""
    # Register user
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpass@example.com", "password": "correctpass"},
    )
    
    # Login with wrong password
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "wrongpass@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, auth_headers: dict):
    """Test getting current user when authenticated."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    """Test getting current user without auth fails."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """Test token refresh."""
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@example.com", "password": "testpass123"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "refresh@example.com", "password": "testpass123"},
    )
    assert login_response.status_code == 200
    first = client.cookies["refresh_token"]

    # Refresh with the cookie the login set: it rotates
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert set(response.json()) == {"expires_at"}
    assert client.cookies["refresh_token"] != first


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, auth_headers: dict):
    """Test logout revokes tokens."""
    response = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    assert "logged out" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_logout_revokes_the_cookie_session_and_clears_it(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "bye@example.com", "password": "testpass123"},
    )
    await client.post(
        "/api/v1/auth/login",
        data={"username": "bye@example.com", "password": "testpass123"},
    )
    refresh_token = client.cookies["refresh_token"]

    # No access token needed (it may have expired): only the backend can clear httpOnly cookies
    client.cookies.delete("token")
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert "refresh_token" not in client.cookies and "token_exp" not in client.cookies

    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_confirmed_tv_gets_its_session_as_cookies(client: AsyncClient, test_session):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models.user import DeviceCode, User

    user = User(email="tv@example.com", password_hash="x")
    test_session.add(user)
    await test_session.flush()
    test_session.add(DeviceCode(
        user_code="ABC123", device_code="dev-code", user_id=user.id, confirmed=True,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    ))
    await test_session.commit()

    response = await client.get("/api/v1/auth/device/poll", params={"device_code": "dev-code"})

    assert response.status_code == 200
    assert response.json() == {"status": "confirmed"}
    assert {"token", "refresh_token", "token_exp"} <= set(client.cookies.keys())
    assert (await client.get("/api/v1/auth/me")).json()["email"] == "tv@example.com"
    assert (await test_session.execute(select(DeviceCode))).scalars().all() == []  # used up
