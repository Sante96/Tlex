"""The player's client ring: how many Telegram clients the title's stream holds now."""

from unittest.mock import MagicMock

from httpx import AsyncClient

from app.services.streaming import manager


async def test_clients_of_a_playing_title(client: AsyncClient, auth_headers, mocker):
    reader = MagicMock(_clients=[object(), object(), object()])
    mocker.patch.dict(manager._reader_cache, {(42, ""): (reader, 0.0)})
    mocker.patch(
        "app.api.v1.stream.worker_manager.pool_status", return_value={"total_clients": 10}
    )

    resp = await client.get("/api/v1/stream/clients/42", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json() == {"in_use": 3, "total": 10}


async def test_a_title_not_playing_holds_none(client: AsyncClient, auth_headers, mocker):
    mocker.patch(
        "app.api.v1.stream.worker_manager.pool_status", return_value={"total_clients": 10}
    )

    resp = await client.get("/api/v1/stream/clients/7", headers=auth_headers)

    assert resp.json() == {"in_use": 0, "total": 10}


async def test_clients_need_login(client: AsyncClient):
    assert (await client.get("/api/v1/stream/clients/42")).status_code == 401


async def test_each_viewer_sees_its_own_clients(client: AsyncClient, auth_headers, mocker):
    mocker.patch.dict(manager._reader_cache, {(42, "tablet"): (MagicMock(_clients=[1, 2]), 0.0)})
    mocker.patch(
        "app.api.v1.stream.worker_manager.pool_status", return_value={"total_clients": 10}
    )

    tablet = await client.get("/api/v1/stream/clients/42?v=tablet", headers=auth_headers)
    phone = await client.get("/api/v1/stream/clients/42?v=phone", headers=auth_headers)

    assert tablet.json()["in_use"] == 2 and phone.json()["in_use"] == 0


async def test_a_viewer_id_is_a_short_token(client: AsyncClient, auth_headers):
    # It goes into the internal URL ffmpeg reads
    resp = await client.get("/api/v1/stream/clients/42?v=a%26internal%3Dx", headers=auth_headers)
    assert resp.status_code == 422
