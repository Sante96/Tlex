"""Continue Watching carries what the home's landscape cards and hero draw."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType, Series


async def test_episode_and_movie_cards_get_a_still_and_an_overview(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    show = Series(title="Show", poster_path="/show-poster.jpg", backdrop_path="/show-backdrop.jpg",
                  overview="The show.")
    test_session.add(show)
    await test_session.flush()
    episode = MediaItem(title="Pilot", media_type=MediaType.EPISODE, series_id=show.id, season_number=1,
                        episode_number=2, poster_path="/pilot-still.jpg", overview="The pilot.",
                        duration_seconds=1000)
    film = MediaItem(title="Film", media_type=MediaType.MOVIE, poster_path="/film-poster.jpg",
                     backdrop_path="/film-backdrop.jpg", overview="The film.", duration_seconds=100)
    test_session.add_all([episode, film])
    await test_session.commit()

    for item, total in ((episode, 1000), (film, 100)):
        await client.put(f"/api/v1/progress/{item.id}",
                         json={"position_seconds": total // 4, "duration_seconds": total}, headers=auth_headers)
    cards = {c["id"]: c for c in (await client.get("/api/v1/progress", headers=auth_headers)).json()}

    # The episode's own still (stored as its poster), not the series poster the card used
    assert cards[episode.id]["still_path"] == "/pilot-still.jpg"
    assert cards[episode.id]["poster_path"] == "/show-poster.jpg"
    assert cards[episode.id]["overview"] == "The pilot."
    # A movie has no still: its backdrop is the landscape picture
    assert cards[film.id]["still_path"] == "/film-backdrop.jpg"
    assert cards[film.id]["overview"] == "The film."
