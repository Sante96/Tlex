"""Anime: Japanese animation by TMDB (Animation + Japanese), a section of its own."""

from unittest.mock import AsyncMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType, Series
from app.services.tmdb import tmdb_client
from app.services.tmdb.models import MovieDetails, TVDetails


def _tv(genres: list[tuple[int, str]], language: str) -> dict:
    return {
        "id": 1,
        "name": "Show",
        "genres": [{"id": i, "name": n} for i, n in genres],
        "original_language": language,
        "content_ratings": {"results": []},
    }


async def test_tmdb_tells_japanese_animation_apart(mocker):
    get = mocker.patch.object(tmdb_client, "_get", new=AsyncMock())

    get.return_value = _tv([(16, "Animazione"), (10765, "Sci-Fi & Fantasy")], "ja")
    frieren = await tmdb_client.get_tv_details(1)
    # Animation too, but in English: a series, not an anime
    get.return_value = _tv([(16, "Animazione"), (35, "Commedia")], "en")
    rick_and_morty = await tmdb_client.get_tv_details(1)
    # Japanese, not animated: a drama
    get.return_value = _tv([(18, "Dramma")], "ja")
    drama = await tmdb_client.get_tv_details(1)

    assert frieren and rick_and_morty and drama
    assert (frieren.anime, frieren.original_language) == (True, "ja")
    assert rick_and_morty.anime is False
    assert drama.anime is False


async def _library(test_session: AsyncSession):
    anime_show, show = (
        Series(title="Frieren", is_anime=True),
        Series(title="Rick and Morty"),
    )
    test_session.add_all([anime_show, show])
    await test_session.flush()
    test_session.add_all([
        MediaItem(title="Ep", media_type=MediaType.EPISODE, series_id=anime_show.id),
        MediaItem(title="Ep", media_type=MediaType.EPISODE, series_id=show.id),
    ])
    anime_film = MediaItem(title="A Silent Voice", media_type=MediaType.MOVIE, is_anime=True)
    film = MediaItem(title="Balle spaziali", media_type=MediaType.MOVIE)
    test_session.add_all([anime_film, film])
    await test_session.commit()
    return anime_show, show, anime_film, film


async def test_anime_leave_series_and_films_for_their_own_section(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    anime_show, show, anime_film, film = await _library(test_session)

    series = await client.get("/api/v1/series", params={"anime": "false"}, headers=auth_headers)
    films = await client.get(
        "/api/v1/media", params={"media_type": "MOVIE", "anime": "false"}, headers=auth_headers
    )
    anime = await client.get("/api/v1/anime", params={"sort": "title"}, headers=auth_headers)

    assert [s["title"] for s in series.json()["items"]] == ["Rick and Morty"]
    assert [f["title"] for f in films.json()["items"]] == ["Balle spaziali"]
    assert [(a["kind"], a["title"]) for a in anime.json()["items"]] == [
        ("movie", "A Silent Voice"),
        ("series", "Frieren"),
    ]
    assert anime.json()["total"] == 2
    # Without the filter (search, the watchlist): everything, as before
    every = await client.get("/api/v1/series", headers=auth_headers)
    assert len(every.json()["items"]) == 2


async def test_anime_newest_first_mixes_series_and_films(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    anime_show, _, anime_film, _ = await _library(test_session)
    # The series gets an episode after the film: it comes first
    test_session.add(MediaItem(title="New", media_type=MediaType.EPISODE, series_id=anime_show.id))
    await test_session.commit()

    anime = await client.get("/api/v1/anime", params={"sort": "recent"}, headers=auth_headers)

    assert [a["title"] for a in anime.json()["items"]] == ["Frieren", "A Silent Voice"]


async def test_an_admin_overrides_tmdb_and_can_go_back_to_it(
    client: AsyncClient, admin_headers: dict, auth_headers: dict, test_session: AsyncSession
):
    _, show, _, film = await _library(test_session)

    assert (
        await client.put(f"/api/v1/series/{show.id}/anime", json={"anime": True}, headers=auth_headers)
    ).status_code == 403
    await client.put(f"/api/v1/series/{show.id}/anime", json={"anime": True}, headers=admin_headers)
    await client.put(f"/api/v1/media/{film.id}/anime", json={"anime": True}, headers=admin_headers)

    titles = {a["title"] for a in (await client.get("/api/v1/anime", headers=admin_headers)).json()["items"]}
    assert {"Rick and Morty", "Balle spaziali"} <= titles
    detail = (await client.get(f"/api/v1/series/{show.id}", headers=admin_headers)).json()
    assert (detail["is_anime"], detail["anime_override"]) == (True, True)

    # null: back to what TMDB says
    await client.put(f"/api/v1/series/{show.id}/anime", json={"anime": None}, headers=admin_headers)
    titles = {a["title"] for a in (await client.get("/api/v1/anime", headers=admin_headers)).json()["items"]}
    assert "Rick and Morty" not in titles


async def test_the_library_is_classified_once_from_tmdb(test_session: AsyncSession, mocker):
    from app.services.anime import classify_library

    show = Series(title="Frieren", tmdb_id=209867)
    film = MediaItem(title="Balle spaziali", media_type=MediaType.MOVIE, tmdb_id=10663)
    done = Series(title="Done", tmdb_id=1, original_language="en")
    test_session.add_all([show, film, done])
    await test_session.commit()
    tv = mocker.patch.object(
        tmdb_client,
        "get_tv_details",
        new=AsyncMock(
            return_value=TVDetails(
                tmdb_id=209867, title="Frieren", overview=None, poster_path=None,
                backdrop_path=None, first_air_date=None, genres=["Animazione"],
                vote_average=8.9, content_rating=None, original_language="ja", anime=True,
            )
        ),
    )
    mocker.patch.object(
        tmdb_client,
        "get_movie_full_details",
        new=AsyncMock(
            return_value=MovieDetails(
                tmdb_id=10663, title="Balle spaziali", overview=None, poster_path=None,
                backdrop_path=None, release_date=None, genres=["Commedia", "Fantascienza"],
                vote_average=7.0, content_rating=None, original_language="en", anime=False,
            )
        ),
    )

    assert await classify_library(test_session) == 2

    await test_session.refresh(show)
    await test_session.refresh(film)
    assert (show.is_anime, show.original_language) == (True, "ja")
    # A film's genres too: until now only "Update metadata" filled them in
    assert (film.is_anime, film.genres) == (False, "Commedia,Fantascienza")
    tv.assert_awaited_once()  # the one already classified is left alone
