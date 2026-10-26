"""Where the credits start (the player's Up next shows there), and the films it suggests."""

from unittest.mock import AsyncMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType, Series


async def _credits(client: AsyncClient, headers: dict, media_id: int) -> tuple:
    data = (await client.get(f"/api/v1/media/{media_id}", headers=headers)).json()
    return data["credits_start"], data["credits_start_seconds"]


async def test_credits_set_by_hand_and_cleared(
    client: AsyncClient, admin_headers: dict, test_session: AsyncSession
):
    film = MediaItem(title="Film", media_type=MediaType.MOVIE, duration_seconds=6000)
    test_session.add(film)
    await test_session.commit()

    response = await client.put(
        f"/api/v1/media/{film.id}/credits", json={"seconds": 5600}, headers=admin_headers
    )

    assert response.status_code == 200
    assert await _credits(client, admin_headers, film.id) == (5600, 5600)
    await client.put(
        f"/api/v1/media/{film.id}/credits", json={"seconds": None}, headers=admin_headers
    )
    # No point: the player falls back to its 30 s before the end
    assert await _credits(client, admin_headers, film.id) == (None, None)


async def test_only_an_admin_sets_the_credits(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    film = MediaItem(title="Film", media_type=MediaType.MOVIE, duration_seconds=6000)
    test_session.add(film)
    await test_session.commit()

    response = await client.put(
        f"/api/v1/media/{film.id}/credits", json={"seconds": 5600}, headers=auth_headers
    )

    assert response.status_code == 403


async def test_a_credits_chapter_marks_them(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    episode = MediaItem(
        title="Ep",
        media_type=MediaType.EPISODE,
        duration_seconds=1420,
        chapters=[
            {"start": 0, "end": 90, "title": "Opening"},
            {"start": 90, "end": 1300, "title": "Part A"},
            {"start": 1300, "end": 1420, "title": "Ending"},
        ],
    )
    test_session.add(episode)
    await test_session.commit()

    assert await _credits(client, auth_headers, episode.id) == (1300, None)


async def test_an_episode_takes_its_neighbour_s_credits_length(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    show = Series(title="Show")
    test_session.add(show)
    await test_session.flush()
    marked, near, far, unmarked = (
        MediaItem(
            title=f"E{n}",
            media_type=MediaType.EPISODE,
            series_id=show.id,
            season_number=1,
            episode_number=n,
            duration_seconds=d,
            credits_start_seconds=c,
        )
        for n, d, c in ((1, 2700, 2400), (3, 2650, 2380), (9, 2000, 1000), (4, 2720, None))
    )
    test_session.add_all([marked, near, far, unmarked])
    await test_session.commit()

    # Episode 3 is the nearest marked one: its 270 s of credits, from this one's end
    assert await _credits(client, auth_headers, unmarked.id) == (2720 - 270, None)


async def test_progress_counts_as_watched_from_the_credits(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    # The credits take 8% of it: before them it was never "watched" at 90%
    film = MediaItem(
        title="Film", media_type=MediaType.MOVIE, duration_seconds=6000, credits_start_seconds=5520
    )
    test_session.add(film)
    await test_session.commit()

    response = await client.put(
        f"/api/v1/progress/{film.id}",
        json={"position_seconds": 5530, "duration_seconds": 6000},
        headers=auth_headers,
    )

    assert response.json()["completed"] is True


async def test_recommendations_tmdb_first_then_shared_genres(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession, mocker
):
    from app.services.tmdb import tmdb_client

    def film(title: str, tmdb_id: int, genres: str) -> MediaItem:
        return MediaItem(
            title=title,
            media_type=MediaType.MOVIE,
            tmdb_id=tmdb_id,
            genres=genres,
            backdrop_path=f"/{title}.jpg",
        )

    watched = film("Watched", 1, "Action,Comedy")
    library = [
        film("TMDB pick", 2, "Drama"),
        film("Same genres", 3, "Action,Comedy"),
        film("One genre", 4, "Comedy,Horror"),
        film("Nothing shared", 5, "Documentary"),
    ]
    test_session.add_all([watched, *library])
    await test_session.commit()
    mocker.patch.object(
        tmdb_client, "get_movie_recommendations", new=AsyncMock(return_value=[99, 2])
    )

    response = await client.get(f"/api/v1/media/{watched.id}/recommendations", headers=auth_headers)

    assert response.status_code == 200
    assert [r["title"] for r in response.json()] == ["TMDB pick", "Same genres", "One genre"]
