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
    assert data["is_admin"] is False


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
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


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
    refresh_token = login_response.json()["refresh_token"]
    
    # Refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, auth_headers: dict):
    """Test logout revokes tokens."""
    response = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    assert "logged out" in response.json()["message"].lower()
