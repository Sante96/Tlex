"""Own images (concerts and their franchises): uploaded, or downloaded from a pasted link."""

import asyncio
import re

import httpx
import pytest
from httpx import AsyncClient

from app.services import images
from app.services.images import ImageError, fetch_image

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
NAME = re.compile(r"^local:([0-9a-f]{32}\.png)$")


@pytest.fixture(autouse=True)
def images_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "IMAGES_DIR", tmp_path)
    return tmp_path


def _upload(data: bytes, name: str = "poster.png") -> dict:
    return {"file": (name, data, "application/octet-stream")}


async def test_upload_png_is_saved_and_served(client: AsyncClient, auth_headers, images_dir):
    resp = await client.post("/api/v1/images", files=_upload(PNG), headers=auth_headers)

    assert resp.status_code == 200
    match = NAME.match(resp.json()["path"])
    assert match
    served = await client.get(f"/api/v1/images/{match.group(1)}")  # no auth header
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == PNG


async def test_upload_rejects_non_images_and_oversize(
    client: AsyncClient, auth_headers, images_dir
):
    html = await client.post("/api/v1/images", files=_upload(b"<html>"), headers=auth_headers)
    huge = b"\xff\xd8\xff" + bytes(images.MAX_IMAGE_BYTES)
    big = await client.post("/api/v1/images", files=_upload(huge), headers=auth_headers)

    assert (html.status_code, big.status_code) == (400, 400)
    assert html.json()["detail"]
    assert not list(images_dir.iterdir())


async def test_upload_needs_login(client: AsyncClient):
    resp = await client.post("/api/v1/images", files=_upload(PNG))
    assert resp.status_code == 401


@pytest.mark.parametrize("name", ["..%2Fsecret.png", "abc.png", "0" * 32 + ".svg", "0" * 32 + ".png"])
async def test_get_rejects_other_names(client: AsyncClient, images_dir, name):
    (images_dir / "secret.png").write_bytes(PNG)
    resp = await client.get(f"/api/v1/images/{name}")
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x.png",
        "http://localhost/x.png",
        "http://10.0.0.5/x.png",
        "http://169.254.169.254/latest",
        "ftp://example.com/x.png",
    ],
)
async def test_from_url_refuses_internal_addresses(
    client: AsyncClient, auth_headers, monkeypatch, images_dir, url
):
    def no_requests(*args, **kwargs):
        raise AssertionError("no request may leave for this address")

    monkeypatch.setattr(images.httpx, "AsyncClient", no_requests)

    resp = await client.post("/api/v1/images/from-url", json={"url": url}, headers=auth_headers)

    assert resp.status_code == 400
    assert not list(images_dir.iterdir())


def _public_dns(monkeypatch, address="93.184.216.34"):
    monkeypatch.setattr(
        images.socket, "getaddrinfo", lambda host, *a, **k: [(2, 1, 6, "", (address, 0))]
    )


async def test_from_url_saves_a_remote_image(monkeypatch):
    _public_dns(monkeypatch)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    )

    assert await fetch_image("https://example.com/poster.png", transport=transport) == PNG


async def test_from_url_rechecks_every_redirect(monkeypatch):
    hosts = {"example.com": "93.184.216.34", "127.0.0.1": "127.0.0.1"}
    monkeypatch.setattr(
        images.socket, "getaddrinfo", lambda host, *a, **k: [(2, 1, 6, "", (hosts[host], 0))]
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "http://127.0.0.1/admin.png"})
    )

    with pytest.raises(ImageError):
        await fetch_image("https://example.com/poster.png", transport=transport)


async def test_from_url_stops_past_the_size_limit(monkeypatch):
    _public_dns(monkeypatch)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=PNG + bytes(images.MAX_IMAGE_BYTES))
    )

    with pytest.raises(ImageError):
        await fetch_image("https://example.com/huge.png", transport=transport)


async def test_from_url_unreachable_link_is_a_clear_error(monkeypatch):
    _public_dns(monkeypatch)

    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(ImageError):
        await fetch_image("https://example.com/p.png", transport=httpx.MockTransport(refuse))


async def test_from_url_gives_up_after_the_deadline(monkeypatch):
    _public_dns(monkeypatch)
    monkeypatch.setattr(images, "DOWNLOAD_DEADLINE", 0.05)

    async def drip(request):
        await asyncio.sleep(1)
        return httpx.Response(200, content=PNG)

    with pytest.raises(ImageError):
        await fetch_image("https://example.com/p.png", transport=httpx.MockTransport(drip))


async def test_from_url_endpoint_saves_what_it_fetched(
    client: AsyncClient, auth_headers, monkeypatch, images_dir
):
    async def fetched(url, transport=None):
        return PNG

    monkeypatch.setattr("app.api.v1.images.fetch_image", fetched)

    resp = await client.post(
        "/api/v1/images/from-url", json={"url": "https://example.com/p.png"}, headers=auth_headers
    )

    assert resp.status_code == 200
    assert NAME.match(resp.json()["path"])
    assert len(list(images_dir.iterdir())) == 1
