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


async def test_the_poll_reports_how_much_of_the_stream_was_read(client: AsyncClient, auth_headers, mocker):
    from app.api.v1 import stream

    mocker.patch.dict(stream._read, {}, clear=True)
    mocker.patch(
        "app.api.v1.stream.worker_manager.pool_status", return_value={"total_clients": 10}
    )

    await client.get("/api/v1/stream/clients/42?v=tab1&read=1234", headers=auth_headers)

    assert stream._read == {(42, "tab1"): 1234}


async def test_play_waits_for_the_page_to_read(mocker):
    # Safari keeps downloading a fetch body the page doesn't read: 600 MB in 3 minutes
    # piled up in its memory, and iOS reloaded the page. /play stops MAX_UNREAD ahead
    import asyncio

    from app.api.v1 import stream

    mocker.patch.object(stream, "MAX_UNREAD", 3)
    mocker.patch.dict(stream._read, {(42, "tab1"): 0}, clear=True)

    async def chunks():
        for _ in range(10):
            yield b"x"

    sent = []

    async def consume():
        async for chunk in stream._paced(chunks(), (42, "tab1")):
            sent.append(chunk)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.6)
    assert len(sent) == 4  # 3 unread allowed, the 4th goes as the limit is checked first

    stream._read[(42, "tab1")] = 10  # the page read it all
    await asyncio.wait_for(task, 2)
    assert len(sent) == 10


async def test_a_page_that_never_reports_is_not_held(mocker):
    # An older player without the report: no flow control rather than a stuck stream
    from app.api.v1 import stream

    mocker.patch.object(stream, "MAX_UNREAD", 3)
    mocker.patch.dict(stream._read, {}, clear=True)

    async def chunks():
        for _ in range(10):
            yield b"x"

    assert len([c async for c in stream._paced(chunks(), (42, "tab1"))]) == 10
