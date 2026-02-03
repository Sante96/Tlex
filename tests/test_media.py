"""Tests for media endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType


@pytest.fixture
async def sample_movies(test_session: AsyncSession) -> list[MediaItem]:
    """Create sample movies for testing."""
    movies = [
        MediaItem(
            title="Movie One",
            media_type=MediaType.MOVIE,
            total_size=1000000,
            overview="First movie description",
        ),
        MediaItem(
            title="Movie Two",
            media_type=MediaType.MOVIE,
            total_size=2000000,
            overview="Second movie description",
        ),
    ]
    for movie in movies:
        test_session.add(movie)
    await test_session.commit()
    for movie in movies:
        await test_session.refresh(movie)
    return movies


@pytest.mark.asyncio
async def test_list_media(client: AsyncClient, sample_movies: list[MediaItem]):
    """Test listing media items."""
    response = await client.get("/api/v1/media/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_media_with_type_filter(
    client: AsyncClient, sample_movies: list[MediaItem]
):
    """Test listing media with type filter."""
    response = await client.get("/api/v1/media/?media_type=MOVIE")
    assert response.status_code == 200
    data = response.json()
    assert all(item["media_type"] == "MOVIE" for item in data["items"])


@pytest.mark.asyncio
async def test_get_media_detail(client: AsyncClient, sample_movies: list[MediaItem]):
    """Test getting media details."""
    media_id = sample_movies[0].id
    response = await client.get(f"/api/v1/media/{media_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Movie One"
    assert data["overview"] == "First movie description"


@pytest.mark.asyncio
async def test_get_media_not_found(client: AsyncClient):
    """Test getting non-existent media."""
    response = await client.get("/api/v1/media/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_media_requires_admin(
    client: AsyncClient, auth_headers: dict, sample_movies: list[MediaItem]
):
    """Test deleting media requires admin."""
    media_id = sample_movies[0].id
    response = await client.delete(
        f"/api/v1/media/{media_id}",
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_media_as_admin(
    client: AsyncClient, admin_headers: dict, sample_movies: list[MediaItem]
):
    """Test admin can delete media."""
    media_id = sample_movies[0].id
    response = await client.delete(
        f"/api/v1/media/{media_id}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    
    # Verify deleted
    get_response = await client.get(f"/api/v1/media/{media_id}")
    assert get_response.status_code == 404
