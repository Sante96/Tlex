"""Continue Watching carries what the home's landscape cards and hero draw."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType, Series


async def test_episode_and_movie_cards_get_a_still_and_an_overview(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    show = Series(
        title="Show",
        poster_path="/show-poster.jpg",
        backdrop_path="/show-backdrop.jpg",
        overview="The show.",
    )
    test_session.add(show)
    await test_session.flush()
    episode = MediaItem(
        title="Pilot",
        media_type=MediaType.EPISODE,
        series_id=show.id,
        season_number=1,
        episode_number=2,
        poster_path="/pilot-still.jpg",
        overview="The pilot.",
        duration_seconds=1000,
    )
    film = MediaItem(
        title="Film",
        media_type=MediaType.MOVIE,
        poster_path="/film-poster.jpg",
        backdrop_path="/film-backdrop.jpg",
        overview="The film.",
        duration_seconds=100,
    )
    test_session.add_all([episode, film])
    await test_session.commit()

    for item, total in ((episode, 1000), (film, 100)):
        await client.put(
            f"/api/v1/progress/{item.id}",
            json={"position_seconds": total // 4, "duration_seconds": total},
            headers=auth_headers,
        )
    cards = {
        c["id"]: c for c in (await client.get("/api/v1/progress", headers=auth_headers)).json()
    }

    # The episode's own still (stored as its poster), not the series poster the card used
    assert cards[episode.id]["still_path"] == "/pilot-still.jpg"
    assert cards[episode.id]["poster_path"] == "/show-poster.jpg"
    assert cards[episode.id]["overview"] == "The pilot."
    # A movie has no still: its backdrop is the landscape picture
    assert cards[film.id]["still_path"] == "/film-backdrop.jpg"
    assert cards[film.id]["overview"] == "The film."


async def _watch(client: AsyncClient, headers: dict, item: MediaItem, position: int = 250):
    await client.put(
        f"/api/v1/progress/{item.id}",
        json={"position_seconds": position, "duration_seconds": 1000},
        headers=headers,
    )


async def _continue_ids(client: AsyncClient, headers: dict) -> list[int]:
    return [c["id"] for c in (await client.get("/api/v1/progress", headers=headers)).json()]


async def test_a_removed_title_keeps_its_place_until_watched_again(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    film, other = (MediaItem(title=t, media_type=MediaType.MOVIE) for t in ("Film", "Other"))
    test_session.add_all([film, other])
    await test_session.commit()
    await _watch(client, auth_headers, film)
    await _watch(client, auth_headers, other)

    response = await client.post(f"/api/v1/progress/{film.id}/hide", headers=auth_headers)

    assert response.status_code == 200
    assert await _continue_ids(client, auth_headers) == [other.id]
    # The player asks where to start from: the place is still there
    progress = (await client.get(f"/api/v1/progress/{film.id}", headers=auth_headers)).json()
    assert (progress["position_seconds"], progress["hidden"]) == (250, True)
    # Watching it again brings it back
    await _watch(client, auth_headers, film, position=10)
    assert film.id in await _continue_ids(client, auth_headers)
    progress = (await client.get(f"/api/v1/progress/{film.id}", headers=auth_headers)).json()
    assert progress["hidden"] is False


async def test_removing_an_episode_removes_its_whole_series(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    show, other_show = Series(title="Show"), Series(title="Other show")
    test_session.add_all([show, other_show])
    await test_session.flush()
    first, second, finished, elsewhere = (
        MediaItem(title=t, media_type=MediaType.EPISODE, series_id=s.id, season_number=1, episode_number=n)
        for t, s, n in (("E1", show, 1), ("E2", show, 2), ("E3", show, 3), ("X1", other_show, 1))
    )
    test_session.add_all([first, second, finished, elsewhere])
    await test_session.commit()
    for episode in (first, second, elsewhere):
        await _watch(client, auth_headers, episode)
    await _watch(client, auth_headers, finished, position=950)
    shown = next(i for i in await _continue_ids(client, auth_headers) if i != elsewhere.id)

    await client.post(f"/api/v1/progress/{shown}/hide", headers=auth_headers)

    # Not the series' other started episode in its place
    assert await _continue_ids(client, auth_headers) == [elsewhere.id]
    # A finished episode stays watched, untouched
    done = (await client.get(f"/api/v1/progress/{finished.id}", headers=auth_headers)).json()
    assert (done["completed"], done["hidden"]) == (True, False)


async def test_removing_an_unknown_title_is_a_404(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/progress/999999/hide", headers=auth_headers)
    assert response.status_code == 404
