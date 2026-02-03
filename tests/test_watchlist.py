"""Tests for watchlist endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType


@pytest.fixture
async def sample_media(test_session: AsyncSession) -> MediaItem:
    """Create a sample media item for testing."""
    media = MediaItem(
        title="Test Movie",
        media_type=MediaType.MOVIE,
        total_size=1000000,
    )
    test_session.add(media)
    await test_session.commit()
    await test_session.refresh(media)
    return media


@pytest.mark.asyncio
async def test_get_empty_watchlist(client: AsyncClient, auth_headers: dict):
    """Test getting empty watchlist."""
    response = await client.get("/api/v1/watchlist/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_add_to_watchlist(
    client: AsyncClient, auth_headers: dict, sample_media: MediaItem
):
    """Test adding media to watchlist."""
    response = await client.post(
        f"/api/v1/watchlist/{sample_media.id}",
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert "added" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_add_duplicate_to_watchlist(
    client: AsyncClient, auth_headers: dict, sample_media: MediaItem
):
    """Test adding duplicate to watchlist fails."""
    # Add first time
    await client.post(
        f"/api/v1/watchlist/{sample_media.id}",
        headers=auth_headers,
    )
    
    # Add second time
    response = await client.post(
        f"/api/v1/watchlist/{sample_media.id}",
        headers=auth_headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_check_watchlist_status(
    client: AsyncClient, auth_headers: dict, sample_media: MediaItem
):
    """Test checking watchlist status."""
    # Not in watchlist
    response = await client.get(
        f"/api/v1/watchlist/{sample_media.id}/status",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["in_watchlist"] is False
    
    # Add to watchlist
    await client.post(
        f"/api/v1/watchlist/{sample_media.id}",
        headers=auth_headers,
    )
    
    # Now in watchlist
    response = await client.get(
        f"/api/v1/watchlist/{sample_media.id}/status",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["in_watchlist"] is True


@pytest.mark.asyncio
async def test_remove_from_watchlist(
    client: AsyncClient, auth_headers: dict, sample_media: MediaItem
):
    """Test removing from watchlist."""
    # Add first
    await client.post(
        f"/api/v1/watchlist/{sample_media.id}",
        headers=auth_headers,
    )
    
    # Remove
    response = await client.delete(
        f"/api/v1/watchlist/{sample_media.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    
    # Verify removed
    status_response = await client.get(
        f"/api/v1/watchlist/{sample_media.id}/status",
        headers=auth_headers,
    )
    assert status_response.json()["in_watchlist"] is False


@pytest.mark.asyncio
async def test_watchlist_requires_auth(client: AsyncClient):
    """Test watchlist endpoints require authentication."""
    response = await client.get("/api/v1/watchlist/")
    assert response.status_code == 401
