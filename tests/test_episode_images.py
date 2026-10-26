"""Episode pictures: a refreshed series brings its episodes' stills, and a user's own still
shows where the episodes are listed."""

from unittest.mock import AsyncMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType, Series
from app.models.user import User, UserMediaOverride
from app.services.tmdb import tmdb_client
from app.services.tmdb.models import EpisodeInfo, TMDBResult, TVDetails


async def _show(test_session: AsyncSession):
    show = Series(title="Laid-Back Camp", tmdb_id=95623)
    test_session.add(show)
    await test_session.flush()
    episodes = [
        MediaItem(
            title=f"Ep {n}", media_type=MediaType.EPISODE, series_id=show.id, tmdb_id=95623,
            season_number=1, episode_number=n, poster_path=f"/drama-{n}.jpg",
            backdrop_path="/drama.jpg",
        )
        for n in (1, 2)
    ]
    test_session.add_all(episodes)
    await test_session.commit()
    return show, episodes


async def test_a_refresh_brings_the_episodes_stills_too(
    client: AsyncClient, admin_headers: dict, test_session: AsyncSession, mocker
):
    # Re-matched from a live-action drama to the anime: the titles changed, the episodes
    # kept the drama's stills
    show, episodes = await _show(test_session)
    mocker.patch.object(
        tmdb_client, "search_tv",
        new=AsyncMock(return_value=TMDBResult(
            tmdb_id=76075, title="Laid-Back Camp", overview=None, poster_path="/p.jpg",
            backdrop_path="/anime.jpg", release_date="2018-01-04", media_type="tv",
        )),
    )
    mocker.patch.object(
        tmdb_client, "get_tv_details",
        new=AsyncMock(return_value=TVDetails(
            tmdb_id=76075, title="Laid-Back Camp", overview=None, poster_path=None,
            backdrop_path=None, first_air_date=None, genres=["Animazione"], vote_average=None,
            content_rating=None, original_language="ja", anime=True,
        )),
    )
    mocker.patch.object(
        tmdb_client, "get_season_episodes",
        new=AsyncMock(return_value=[
            EpisodeInfo(episode_number=n, name=f"Episodio {n}", overview=None,
                        still_path=f"/anime-{n}.jpg", air_date=None, runtime=None)
            for n in (1, 2)
        ]),
    )

    response = await client.post(f"/api/v1/series/{show.id}/refresh-metadata", headers=admin_headers)

    assert response.status_code == 200
    for ep in episodes:
        await test_session.refresh(ep)
    assert [e.poster_path for e in episodes] == ["/anime-1.jpg", "/anime-2.jpg"]
    assert {e.tmdb_id for e in episodes} == {76075}
    assert {e.backdrop_path for e in episodes} == {"/anime.jpg"}


async def test_a_users_own_still_shows_in_the_episode_list(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    show, episodes = await _show(test_session)
    user = (await test_session.execute(User.__table__.select())).first()
    assert user is not None
    test_session.add(
        UserMediaOverride(user_id=user.id, media_item_id=episodes[0].id, poster_path="/mine.jpg")
    )
    await test_session.commit()

    detail = (await client.get(f"/api/v1/series/{show.id}", headers=auth_headers)).json()
    stills = [e["still_path"] for e in detail["seasons"][0]["episodes"]]
    upcoming = (await client.get(f"/api/v1/media/{episodes[0].id}/next", headers=auth_headers)).json()

    assert stills == ["/mine.jpg", "/drama-2.jpg"]
    assert upcoming["still_path"] == "/drama-2.jpg"  # the next one has none of its own


async def test_an_episode_and_continue_watching_follow_the_users_series_pictures(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    # A new backdrop for Rick and Morty: its episode's page and the home's Continue Watching
    # kept TMDB's (the episode holds its own copy of the series backdrop)
    from app.models.user import UserSeriesOverride

    show, episodes = await _show(test_session)
    user = (await test_session.execute(User.__table__.select())).first()
    assert user is not None
    test_session.add_all([
        UserSeriesOverride(user_id=user.id, series_id=show.id, poster_path="/my-poster.jpg",
                           backdrop_path="/my-backdrop.jpg"),
        UserMediaOverride(user_id=user.id, media_item_id=episodes[1].id, poster_path="/my-still.jpg"),
    ])
    await test_session.commit()
    await client.put(
        f"/api/v1/progress/{episodes[1].id}",
        json={"position_seconds": 100, "duration_seconds": 1000},
        headers=auth_headers,
    )

    episode = (await client.get(f"/api/v1/media/{episodes[0].id}", headers=auth_headers)).json()
    card = (await client.get("/api/v1/progress", headers=auth_headers)).json()[0]

    assert episode["backdrop_path"] == "/my-backdrop.jpg"
    assert (card["backdrop_path"], card["poster_path"], card["still_path"]) == (
        "/my-backdrop.jpg",
        "/my-poster.jpg",
        "/my-still.jpg",
    )
