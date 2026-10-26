"""Concerts through the media API: shared edits, setlist, search by franchise, Continue
Watching."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.models.media import Franchise, MediaItem, MediaType
from app.models.user import Profile, User, WatchProgress
from app.services.ffprobe import ProbeResult, ffprobe_service
from app.services.scanner import processor
from app.services.scanner.models import ScannedFile


async def _concert(session: AsyncSession, **fields) -> MediaItem:
    concert = MediaItem(
        title="Ambience Synesthesia",
        media_type=MediaType.CONCERT,
        franchise=Franchise(key="arknights", title="Arknights"),
        duration_seconds=5940,
        **fields,
    )
    session.add(concert)
    await session.commit()
    return concert


async def test_patch_concert_writes_for_everyone(
    client: AsyncClient, auth_headers, admin_headers, test_session
):
    concert = await _concert(test_session)
    body = {
        "title": "Synesthesia",
        "release_date": "2024-08-03",
        "poster_path": "local:mine.png",
        "setlist": ["Opening", None, "Encore", "extra"],
    }

    resp = await client.patch(f"/api/v1/media/{concert.id}", json=body, headers=auth_headers)

    assert resp.status_code == 200
    other = (await client.get(f"/api/v1/media/{concert.id}", headers=admin_headers)).json()
    assert other["title"] == "Synesthesia"
    assert other["release_date"] == "2024-08-03"
    assert other["poster_path"] == "local:mine.png"
    assert other["setlist"] == ["Opening", None, "Encore", "extra"]
    assert (other["franchise_id"], other["franchise_title"]) == (concert.franchise_id, "Arknights")


async def test_patch_concert_date_can_be_cleared(client: AsyncClient, auth_headers, test_session):
    concert = await _concert(test_session, release_date=date(2024, 1, 1))

    await client.patch(f"/api/v1/media/{concert.id}", json={"release_date": ""}, headers=auth_headers)

    body = (await client.get(f"/api/v1/media/{concert.id}", headers=auth_headers)).json()
    assert body["release_date"] is None


async def test_patch_movie_poster_stays_per_user(
    client: AsyncClient, auth_headers, admin_headers, test_session
):
    film = MediaItem(title="Film", media_type=MediaType.MOVIE, poster_path="/tmdb.jpg")
    test_session.add(film)
    await test_session.commit()

    await client.patch(
        f"/api/v1/media/{film.id}", json={"poster_path": "/mine.jpg"}, headers=auth_headers
    )

    other = (await client.get(f"/api/v1/media/{film.id}", headers=admin_headers)).json()
    assert other["poster_path"] == "/tmdb.jpg"


async def test_analyze_keeps_setlist_and_images(test_session, mocker):
    concert = await _concert(test_session, setlist=["Opening"], poster_path="local:mine.png")
    chapters = [{"start": 0.0, "end": 60.0, "title": None}]
    mocker.patch.object(
        ffprobe_service,
        "analyze_from_telegram",
        new=AsyncMock(return_value=ProbeResult(duration_seconds=60, streams=[], chapters=chapters)),
    )
    first_file = ScannedFile(
        message_id=1, file_id="f", file_name="x.mkv", file_size=1, base_name="x.mkv", channel_id=1
    )

    await processor.analyze_streams(test_session, concert, first_file, MagicMock())
    await test_session.commit()

    row = (
        await test_session.execute(
            select(MediaItem)
            .options(undefer(MediaItem.setlist), undefer(MediaItem.chapters))
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert (row.chapters, row.setlist, row.poster_path) == (chapters, ["Opening"], "local:mine.png")


async def test_patch_concert_refuses_bad_values(client: AsyncClient, auth_headers, test_session):
    concert = await _concert(test_session)

    for body in ({"release_date": "2024-13-40"}, {"title": None}, {"title": "   "}):
        resp = await client.patch(f"/api/v1/media/{concert.id}", json=body, headers=auth_headers)
        assert resp.status_code == 422, body

    after = (await client.get(f"/api/v1/media/{concert.id}", headers=auth_headers)).json()
    assert after["title"] == "Ambience Synesthesia"


async def test_analyze_endpoint_keeps_setlist_and_images(
    client: AsyncClient, admin_headers, test_session, mocker
):
    from app.core.worker_manager import worker_manager
    from app.models.media import MediaPart

    concert = await _concert(test_session, setlist=["Opening"], poster_path="local:mine.png")
    test_session.add(
        MediaPart(
            media_item_id=concert.id,
            telegram_file_id="f",
            part_index=0,
            start_byte=0,
            end_byte=10,
            file_size=10,
            channel_id=-100,
            message_id=1,
        )
    )
    await test_session.commit()
    telegram = MagicMock(get_chat=AsyncMock(side_effect=RuntimeError("offline")))
    mocker.patch.object(
        worker_manager, "get_best_worker", new=AsyncMock(return_value=(MagicMock(), telegram))
    )
    chapters = [{"start": 0.0, "end": 60.0, "title": None}]
    mocker.patch.object(
        ffprobe_service,
        "analyze_from_telegram",
        new=AsyncMock(return_value=ProbeResult(duration_seconds=60, streams=[], chapters=chapters)),
    )

    resp = await client.post(f"/api/v1/media/{concert.id}/analyze", headers=admin_headers)

    assert resp.status_code == 200
    body = (await client.get(f"/api/v1/media/{concert.id}", headers=admin_headers)).json()
    assert (body["chapters"], body["setlist"], body["poster_path"]) == (
        chapters,
        ["Opening"],
        "local:mine.png",
    )


async def test_refresh_metadata_refuses_concerts(
    client: AsyncClient, admin_headers, test_session, mocker
):
    concert = await _concert(test_session, poster_path="local:mine.png")
    from app.services.tmdb import tmdb_client

    search_tv = mocker.patch.object(tmdb_client, "search_tv", new=AsyncMock())

    resp = await client.post(f"/api/v1/media/{concert.id}/refresh-metadata", headers=admin_headers)

    assert resp.status_code == 400
    search_tv.assert_not_called()
    body = (await client.get(f"/api/v1/media/{concert.id}", headers=admin_headers)).json()
    assert (body["title"], body["poster_path"], body["tmdb_id"]) == (
        "Ambience Synesthesia",
        "local:mine.png",
        None,
    )


async def test_search_finds_concerts_by_franchise(client: AsyncClient, auth_headers, test_session):
    await _concert(test_session)
    test_session.add(MediaItem(title="Arknights: the movie", media_type=MediaType.MOVIE))
    await test_session.commit()

    resp = await client.get(
        "/api/v1/media", params={"search": "arkni", "media_type": "CONCERT"}, headers=auth_headers
    )

    body = resp.json()
    assert body["total"] == 1
    assert [i["title"] for i in body["items"]] == ["Ambience Synesthesia"]


async def test_concert_without_poster_shows_its_franchise_poster(
    client: AsyncClient, auth_headers, test_session
):
    concert = MediaItem(
        title="Live",
        media_type=MediaType.CONCERT,
        franchise=Franchise(key="arknights", title="Arknights", poster_path="/f.jpg"),
        backdrop_path="local:frame.jpg",
    )
    test_session.add(concert)
    await test_session.commit()

    detail = (await client.get(f"/api/v1/media/{concert.id}", headers=auth_headers)).json()
    listed = (
        await client.get("/api/v1/media", params={"media_type": "CONCERT"}, headers=auth_headers)
    ).json()["items"][0]

    assert (detail["poster_path"], detail["backdrop_path"]) == ("/f.jpg", "local:frame.jpg")
    assert listed["poster_path"] == "/f.jpg"


async def test_continue_watching_shows_a_concert_like_an_episode(
    client: AsyncClient, auth_headers, test_session
):
    concert = MediaItem(
        title="Live",
        media_type=MediaType.CONCERT,
        franchise=Franchise(
            key="arknights", title="Arknights", poster_path="/f.jpg", backdrop_path="/fb.jpg"
        ),
        backdrop_path="local:frame.jpg",
        duration_seconds=5940,
    )
    test_session.add(concert)
    await test_session.commit()
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
            media_item_id=concert.id,
            position_seconds=600,
            duration_seconds=5940,
        )
    )
    await test_session.commit()

    item = (await client.get("/api/v1/progress", headers=auth_headers)).json()[0]

    # The hero: the franchise's backdrop; its card: the concert's own picture (the frame)
    assert (item["backdrop_path"], item["still_path"], item["poster_path"]) == (
        "/fb.jpg",
        "local:frame.jpg",
        "/f.jpg",
    )


async def test_continue_watching_names_the_franchise(
    client: AsyncClient, auth_headers, test_session
):
    concert = await _concert(test_session)
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
            media_item_id=concert.id,
            position_seconds=600,
            duration_seconds=5940,
        )
    )
    await test_session.commit()

    items = (await client.get("/api/v1/progress", headers=auth_headers)).json()

    assert [(i["media_type"], i["franchise_title"]) for i in items] == [("CONCERT", "Arknights")]
