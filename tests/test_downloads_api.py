"""The Download page's API and the seedbox agent's sync."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.models.download import Download
from app.models.media import MediaItem, MediaPart, MediaType
from app.services.downloads import service
from app.services.scanner.service import scanner_service

TOKEN = "t" * 32
AGENT = {"X-Agent-Token": TOKEN}
MAGNET = "magnet:?xt=urn:btih:ABCDEF&dn=Stargate.SG-1.S01.1080p"


class _same:
    """The test's session as an async context manager (the service opens its own)."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def setup(monkeypatch, test_session):
    settings = get_settings()
    monkeypatch.setattr(settings, "seedbox_agent_token", TOKEN)
    monkeypatch.setattr(settings, "scanner_movies_topic_id", 2)
    monkeypatch.setattr(settings, "scanner_channel_ids", "-100123")
    monkeypatch.setattr(service, "async_session_maker", lambda: _same(test_session))
    monkeypatch.setattr(service, "SCAN_RETRY_SECONDS", 0)


async def _sync(client: AsyncClient, **report) -> dict:
    body = {"free_bytes": 7_000, "dl_speed": 10, "up_speed": 5, **report}
    r = await client.post("/api/v1/downloads/agent/sync", json=body, headers=AGENT)
    assert r.status_code == 200, r.text
    return r.json()


def _torrent(download_id: int, paths: list[str]) -> dict:
    return {
        "download_id": download_id,
        "hash": "abcdef",
        "state": "downloading",
        "progress": 0.5,
        "dlspeed": 1000,
        "upspeed": 0,
        "num_peers": 3,
        "num_seeds": 2,
        "eta": 60,
        "size": 100,
        "files": [{"path": p, "size": 50, "progress": 0.5} for p in paths],
    }


async def _add(client: AsyncClient, headers: dict, magnet: str = MAGNET) -> dict:
    data = {"magnet": magnet, "kind": "series", "name": "Stargate SG-1", "season": "1"}
    r = await client.post("/api/v1/downloads", data=data, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _get(client: AsyncClient, headers: dict, download_id: int) -> dict:
    r = await client.get("/api/v1/downloads", headers=headers)
    return next(d for d in r.json()["downloads"] if d["id"] == download_id)


async def test_downloads_need_a_login_not_an_admin(client: AsyncClient, auth_headers: dict):
    assert (await client.get("/api/v1/downloads")).status_code == 401
    r = await client.get("/api/v1/downloads", headers=auth_headers)
    assert r.status_code == 200
    assert set(r.json()) == {"seedbox", "downloads"}


async def test_adding_a_magnet_queues_it_and_the_agent_gets_it(
    client: AsyncClient, auth_headers: dict
):
    download = await _add(client, auth_headers)
    assert download["status"] == "queued"
    assert download["torrent_name"] == "Stargate.SG-1.S01.1080p"

    commands = await _sync(client)
    assert commands["add"][0]["download_id"] == download["id"]
    assert commands["add"][0]["magnet"] == MAGNET
    assert (await _sync(client))["add"] == []


async def test_the_same_magnet_twice_is_refused(client: AsyncClient, auth_headers: dict):
    await _add(client, auth_headers)
    data = {"magnet": MAGNET, "kind": "film"}
    r = await client.post("/api/v1/downloads", data=data, headers=auth_headers)
    assert r.status_code == 409


async def test_a_broken_torrent_file_is_refused(client: AsyncClient, auth_headers: dict):
    r = await client.post(
        "/api/v1/downloads",
        data={"kind": "film"},
        files={"torrent": ("x.torrent", b"junk", "application/x-bittorrent")},
        headers=auth_headers,
    )
    assert r.status_code == 400


async def test_files_get_their_topics(client: AsyncClient, auth_headers: dict):
    download = await _add(client, auth_headers)
    await _sync(client)
    paths = ["S/Stargate.SG-1.S01E01.mkv", "S/Sample/sample.mkv"]
    await _sync(client, torrents=[_torrent(download["id"], paths)])

    plans = (await _sync(client))["plans"]
    assert plans == [
        {
            "download_id": download["id"],
            "files": [
                {"path": "S/Stargate.SG-1.S01E01.mkv", "topic": "Stargate SG-1 - Stagione 1"}
            ],
        }
    ]
    assert (await _get(client, auth_headers, download["id"]))["status"] == "downloading"


async def test_a_torrent_without_videos_ends_in_error(client: AsyncClient, auth_headers: dict):
    download = await _add(client, auth_headers)
    await _sync(client)
    await _sync(client, torrents=[_torrent(download["id"], ["disc.iso"])])

    shown = await _get(client, auth_headers, download["id"])
    assert shown["status"] == "error"
    assert shown["error"] == "Nessun video da caricare"


async def test_all_files_uploaded_scans_then_removes(
    client: AsyncClient, auth_headers: dict, mocker
):
    scan = mocker.patch.object(
        scanner_service, "scan_all_channels", new=AsyncMock(return_value={"media_created": 2})
    )
    download = await _add(client, auth_headers)
    paths = ["S/Stargate.SG-1.S01E01.mkv", "S/Stargate.SG-1.S01E02.mkv"]
    await _sync(client)
    await _sync(client, torrents=[_torrent(download["id"], paths)])

    uploads = [
        {"download_id": download["id"], "path": p, "topic_id": 77, "message_ids": [i]}
        for i, p in enumerate(paths, start=10)
    ]
    await _sync(client, uploads=uploads)
    await asyncio.gather(*list(service._tasks))

    scan.assert_awaited_once()
    assert scan.await_args is not None and scan.await_args.kwargs["topic_id"] == 77
    assert (await _sync(client))["remove"] == [download["id"]]

    await _sync(client, removed=[download["id"]])
    shown = await _get(client, auth_headers, download["id"])
    assert shown["status"] == "library"
    assert shown["finished_at"] is not None
    assert [f["message_ids"] for f in shown["files"]] == [[10], [11]]


async def test_agent_needs_its_token(client: AsyncClient, monkeypatch):
    url = "/api/v1/downloads/agent/sync"
    body = {"free_bytes": 0, "dl_speed": 0, "up_speed": 0}
    wrong = {"X-Agent-Token": "x" * 32}
    assert (await client.post(url, json=body, headers=wrong)).status_code == 401

    monkeypatch.setattr(get_settings(), "seedbox_agent_token", "")
    assert (await client.post(url, json=body, headers=wrong)).status_code == 404


async def test_the_seedbox_shows_offline_after_30s(client: AsyncClient):
    await _sync(client)
    last_seen = service.seedbox_status()["last_seen"]
    assert service.seedbox_status(now=last_seen + 31)["connected"] is False
    assert service.seedbox_status(now=last_seen + 5)["connected"] is True


async def test_remove_only_touches_the_seedbox(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession, mocker
):
    file = {"size": 50, "topic": "Show - Stagione 1", "topic_id": 77, "progress": 1.0}
    download = Download(
        kind="series",
        name="Show",
        season=1,
        status="library",
        files=[
            {**file, "path": "S/S01E01.mkv", "message_ids": [40], "uploaded": True},
            {**file, "path": "S/S01E02.mkv", "message_ids": [50], "uploaded": False},
        ],
    )
    item = MediaItem(title="Show", media_type=MediaType.EPISODE)
    item.parts.append(
        MediaPart(
            telegram_file_id="f",
            part_index=0,
            start_byte=0,
            end_byte=50,
            file_size=50,
            channel_id=-100123,
            message_id=40,
        )
    )
    test_session.add_all([download, item])
    await test_session.commit()
    telegram = MagicMock()
    telegram.delete_messages = AsyncMock()
    mocker.patch.object(
        worker_manager, "get_best_worker", new=AsyncMock(return_value=(MagicMock(), telegram))
    )

    r = await client.delete(f"/api/v1/downloads/{download.id}", headers=auth_headers)
    assert r.status_code == 204

    telegram.delete_messages.assert_awaited_once_with(-100123, [50])
    assert (await test_session.scalar(select(func.count(MediaItem.id)))) == 1
    assert (await _sync(client))["remove"] == [download.id]


async def test_a_correction_moves_the_plan_and_pause_reaches_the_agent(
    client: AsyncClient, auth_headers: dict
):
    r = await client.post(
        "/api/v1/downloads/preview", data={"magnet": MAGNET}, headers=auth_headers
    )
    assert r.json() == {
        "torrent_name": "Stargate.SG-1.S01.1080p",
        "name": "Stargate SG-1",
        "season": 1,
    }
    download = await _add(client, auth_headers)
    await _sync(client)
    await _sync(client, torrents=[_torrent(download["id"], ["S/Episode 05.mkv"])])

    body = {"kind": "anime", "name": "Stargate", "season": 3}
    r = await client.patch(f"/api/v1/downloads/{download['id']}", json=body, headers=auth_headers)
    assert r.json()["topics"] == ["Stargate - Stagione 3"]
    await client.post(f"/api/v1/downloads/{download['id']}/pause", headers=auth_headers)

    commands = await _sync(client)
    assert commands["pause"] == [download["id"]]
    assert commands["plans"][0]["files"][0]["topic"] == "Stargate - Stagione 3"
    assert (await _sync(client))["pause"] == []


async def test_a_second_torrent_of_the_same_hash_ends_in_error(
    client: AsyncClient, auth_headers: dict
):
    first = await _add(client, auth_headers)
    other = await _add(client, auth_headers, magnet="magnet:?xt=urn:btih:BASE32SPELLING")
    await _sync(client)
    await _sync(
        client,
        torrents=[_torrent(first["id"], ["S/E01.mkv"]), _torrent(other["id"], ["S/E01.mkv"])],
    )

    assert (await _get(client, auth_headers, first["id"]))["status"] == "downloading"
    shown = await _get(client, auth_headers, other["id"])
    assert (shown["status"], shown["error"]) == ("error", "Già in download")


async def test_a_remove_midway_forgets_the_download(client: AsyncClient, auth_headers: dict):
    download = await _add(client, auth_headers)
    await _sync(client)
    await _sync(client, torrents=[_torrent(download["id"], ["S/E01.mkv", "S/E02.mkv"])])

    await client.delete(f"/api/v1/downloads/{download['id']}", headers=auth_headers)
    assert (await _sync(client))["remove"] == [download["id"]]
    await _sync(client, removed=[download["id"]])

    r = await client.get("/api/v1/downloads", headers=auth_headers)
    assert r.json()["downloads"] == []
