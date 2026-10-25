"""Series list counts come from SQL, matching what Series.seasons/episodes_count compute."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType, Series
from app.models.user import Watchlist


async def test_series_list_counts_seasons_and_episodes(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    show, empty = Series(title="A Show"), Series(title="B Empty")
    test_session.add_all([show, empty])
    await test_session.flush()
    # Season numbers 1, 1, 2, None, 0: two real seasons, five episodes
    for n, season in enumerate([1, 1, 2, None, 0], start=1):
        test_session.add(
            MediaItem(
                title=f"Ep {n}", media_type=MediaType.EPISODE, series_id=show.id,
                season_number=season, episode_number=n,
            )
        )
    await test_session.commit()

    response = await client.get("/api/v1/series", headers=auth_headers)

    assert response.status_code == 200
    counts = {s["title"]: (s["seasons_count"], s["episodes_count"]) for s in response.json()["items"]}
    assert counts == {"A Show": (2, 5), "B Empty": (0, 0)}
    await test_session.refresh(show, ["episodes"])
    assert (show.seasons_count, show.episodes_count) == (2, 5)  # same as the model's own count


async def test_watchlist_lists_movies_and_series(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    from app.models.user import User

    user = (await test_session.execute(User.__table__.select())).one()
    movie, show = MediaItem(title="Film", media_type=MediaType.MOVIE), Series(title="Show")
    test_session.add_all([movie, show])
    await test_session.flush()
    test_session.add_all([
        Watchlist(user_id=user.id, media_item_id=movie.id),
        Watchlist(user_id=user.id, series_id=show.id),
    ])
    await test_session.commit()

    response = await client.get("/api/v1/watchlist", headers=auth_headers)

    assert response.status_code == 200
    items = sorted((i["item_type"], i["title"]) for i in response.json()["items"])
    assert items == [("movie", "Film"), ("series", "Show")]
