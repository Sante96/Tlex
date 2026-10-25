"""TMDB client: one shared HTTP client, display data cached, searches always fresh."""

import httpx
import pytest

from app.services.tmdb.client import TMDBClient


@pytest.fixture
def tmdb():
    requests: list[httpx.Request] = []
    status = {"code": 200}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if status["code"] != 200:
            return httpx.Response(status["code"])
        return httpx.Response(200, json={"id": 1, "path": request.url.path, "results": []})

    client = TMDBClient()
    client._http = httpx.AsyncClient(
        base_url="https://api.themoviedb.org/3", transport=httpx.MockTransport(handler)
    )
    return client, requests, status


async def test_display_data_is_cached(tmdb):
    client, requests, _ = tmdb
    first = await client.get_season_details(1, 2, language="it-IT")
    second = await client.get_season_details(1, 2, language="it-IT")
    assert first == second and len(requests) == 1


async def test_language_is_part_of_the_cache_key(tmdb):
    client, requests, _ = tmdb
    await client.get_season_details(1, 2, language="it-IT")
    await client.get_season_details(1, 2, language="en-US")
    assert len(requests) == 2


async def test_searches_and_full_details_are_never_cached(tmdb):
    client, requests, _ = tmdb
    for _ in range(2):
        await client.search_tv("Show")
        await client.get_tv_details(1)
    assert len(requests) == 4


async def test_errors_are_not_cached(tmdb):
    client, requests, status = tmdb
    status["code"] = 500
    assert await client.get_season_details(1, 2) is None
    status["code"] = 200
    assert await client.get_season_details(1, 2) is not None
    assert len(requests) == 2


async def test_one_http_client_for_every_call(tmdb):
    client, _, _ = tmdb
    http = client._client()
    await client.get_trailer(1)
    await client.get_movie_images(1)
    assert client._client() is http
