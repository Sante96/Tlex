"""Profiles keep their own watch progress, Continue Watching and watchlist."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType
from app.models.user import Profile, User


async def _two_profiles(client: AsyncClient, auth_headers: dict, test_session: AsyncSession):
    main = (await test_session.execute(select(Profile))).scalar_one()
    kid = await client.post("/api/v1/profiles", json={"name": "Kid"}, headers=auth_headers)
    film = MediaItem(title="Film", media_type=MediaType.MOVIE, duration_seconds=100)
    test_session.add(film)
    await test_session.commit()
    return main.id, kid.json()["id"], film.id


async def test_progress_and_watchlist_belong_to_the_profile(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    main, kid, film = await _two_profiles(client, auth_headers, test_session)

    client.cookies.set("selected_profile_id", str(main))
    await client.put(
        f"/api/v1/progress/{film}",
        json={"position_seconds": 40, "duration_seconds": 100},
        headers=auth_headers,
    )
    await client.post(f"/api/v1/watchlist/{film}", headers=auth_headers)
    watching_main = (await client.get("/api/v1/progress", headers=auth_headers)).json()

    client.cookies.set("selected_profile_id", str(kid))
    progress_kid = (await client.get(f"/api/v1/progress/{film}", headers=auth_headers)).json()
    watching_kid = (await client.get("/api/v1/progress", headers=auth_headers)).json()
    watchlist_kid = (await client.get("/api/v1/watchlist", headers=auth_headers)).json()

    assert [item["id"] for item in watching_main] == [film]
    assert progress_kid is None and watching_kid == []
    assert watchlist_kid["items"] == []


async def test_a_profile_of_another_user_is_ignored(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    main, _, film = await _two_profiles(client, auth_headers, test_session)
    stranger = User(email="other@example.com", password_hash="x")
    strangers_profile = Profile(name="theirs")
    stranger.profiles.append(strangers_profile)
    test_session.add(stranger)
    await test_session.commit()

    # Someone else's profile id in the cookie: the user's own first profile is used
    client.cookies.set("selected_profile_id", str(strangers_profile.id))
    await client.post(f"/api/v1/watchlist/{film}", headers=auth_headers)

    client.cookies.set("selected_profile_id", str(main))
    titles = [i["title"] for i in (await client.get("/api/v1/watchlist", headers=auth_headers)).json()["items"]]
    assert titles == ["Film"]


async def test_registration_creates_a_first_profile(client: AsyncClient, test_session: AsyncSession):
    await client.post(
        "/api/v1/auth/register", json={"email": "new.person@example.com", "password": "testpass123"}
    )
    profiles = (await test_session.execute(select(Profile.name))).scalars().all()
    assert profiles == ["new.person"]
