"""The franchise pages (an anime/game and its concerts): list, details, shared edits."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import Franchise, MediaItem, MediaType
from app.models.user import Profile, User, WatchProgress


async def _arknights(session: AsyncSession, **franchise) -> tuple[Franchise, MediaItem, MediaItem]:
    arknights = Franchise(key="arknights", title="Arknights", **franchise)
    older = MediaItem(
        title="Ambience Synesthesia 2023",
        media_type=MediaType.CONCERT,
        franchise=arknights,
        release_date=date(2023, 1, 1),
        duration_seconds=5400,
        poster_path="local:a.jpg",
    )
    newer = MediaItem(
        title="Ambience Synesthesia 2024",
        media_type=MediaType.CONCERT,
        franchise=arknights,
        release_date=date(2024, 1, 1),
        duration_seconds=5940,
        poster_path="local:b.jpg",
        backdrop_path="local:b.jpg",
    )
    session.add_all([older, newer])
    await session.commit()
    return arknights, older, newer


async def test_franchise_list_counts_and_falls_back_to_the_latest_concert_image(
    client: AsyncClient, auth_headers, test_session
):
    await _arknights(test_session)
    test_session.add(Franchise(key="genshin", title="Genshin Impact", poster_path="/g.jpg"))
    await test_session.commit()

    body = (await client.get("/api/v1/franchises", headers=auth_headers)).json()

    assert body["total"] == 2
    arknights, genshin = body["items"]
    assert (arknights["title"], arknights["concerts_count"]) == ("Arknights", 2)
    assert (arknights["poster_path"], arknights["backdrop_path"]) == ("local:b.jpg", "local:b.jpg")
    assert (genshin["poster_path"], genshin["concerts_count"]) == ("/g.jpg", 0)


async def test_franchise_detail_lists_concerts_with_progress(
    client: AsyncClient, auth_headers, test_session
):
    arknights, older, newer = await _arknights(test_session, overview="Live shows")
    user = (
        await test_session.execute(select(User).where(User.email == "test@example.com"))
    ).scalar_one()
    profile = (
        await test_session.execute(select(Profile).where(Profile.user_id == user.id))
    ).scalar_one()
    test_session.add(
        WatchProgress(
            user_id=user.id,
            profile_id=profile.id,
            media_item_id=newer.id,
            position_seconds=600,
            duration_seconds=5940,
        )
    )
    await test_session.commit()

    resp = await client.get(f"/api/v1/franchises/{arknights.id}", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert (body["title"], body["overview"]) == ("Arknights", "Live shows")
    assert [c["id"] for c in body["concerts"]] == [newer.id, older.id]  # newest first
    progress = body["concerts"][0]["watch_progress"]
    assert (progress["progress_percent"], progress["is_completed"]) == (10.1, False)
    assert body["concerts"][1]["watch_progress"] is None
    assert body["concerts"][0]["release_date"] == "2024-01-01"


async def test_missing_franchise_is_404(client: AsyncClient, auth_headers):
    assert (await client.get("/api/v1/franchises/999", headers=auth_headers)).status_code == 404


async def test_patch_franchise_is_shared(
    client: AsyncClient, auth_headers, admin_headers, test_session
):
    arknights, _, _ = await _arknights(test_session)

    resp = await client.patch(
        f"/api/v1/franchises/{arknights.id}",
        json={"title": "Arknights Live", "poster_path": "local:mine.png"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    other = (await client.get(f"/api/v1/franchises/{arknights.id}", headers=admin_headers)).json()
    assert (other["title"], other["poster_path"]) == ("Arknights Live", "local:mine.png")


async def test_tmdb_images_empty_without_tmdb(client: AsyncClient, auth_headers, test_session):
    arknights, _, _ = await _arknights(test_session)

    resp = await client.get(f"/api/v1/franchises/{arknights.id}/tmdb-images", headers=auth_headers)

    assert resp.json() == {"stills": [], "posters": [], "backdrops": []}
