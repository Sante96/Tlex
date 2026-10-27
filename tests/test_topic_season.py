"""A topic named "<Title> - Stagione N" holds season N: a file without a season takes it."""

from unittest.mock import AsyncMock

import pytest

from app.services.scanner.models import MediaGroup, ScannedFile
from app.services.scanner.processor import process_group, topic_season
from app.services.tmdb.models import TMDBResult


def test_topic_season_reads_stagione():
    assert topic_season("Stargate SG-1 - Stagione 10") == 10
    assert topic_season("Invincible - Stagione 0") == 0
    assert topic_season("Yuru Camp") is None


def _group(name: str) -> MediaGroup:
    return MediaGroup(
        base_name=name,
        files=[
            ScannedFile(
                message_id=1,
                file_id="f",
                file_name=name,
                file_size=1,
                base_name=name,
                channel_id=-100,
            )
        ],
    )


@pytest.fixture
def tmdb(mocker):
    result = TMDBResult(
        tmdb_id=1,
        title="Show",
        overview=None,
        poster_path=None,
        backdrop_path=None,
        release_date=None,
        media_type="tv",
    )
    mocker.patch(
        "app.services.scanner.processor.tmdb_client.search_tv", AsyncMock(return_value=result)
    )
    mocker.patch(
        "app.services.scanner.processor.tmdb_client.get_tv_details", AsyncMock(return_value=None)
    )
    mocker.patch(
        "app.services.scanner.processor.tmdb_client.get_episode_details",
        AsyncMock(return_value=None),
    )


@pytest.mark.parametrize(
    "name, topic, expected",
    [
        ("[SubsPlease] Sousou no Frieren - 05 (1080p).mkv", "Frieren - Stagione 2", (2, 5)),
        ("Show.S01E03.mkv", "Show - Stagione 3", (3, 3)),
        (
            "Rakuen_Kumachi_Yuru_Camp△_OVA01_Heya_Camp_BD_1080p.mkv",
            "Yuru Camp - Stagione 1",
            (0, 1),
        ),
    ],
    ids=[
        "a_file_without_season_takes_the_topics",
        "the_topic_wins_over_the_files_season",
        "a_special_stays_in_season_0",
    ],
)
async def test_process_group_season(test_session, tmdb, name, topic, expected):
    item = await process_group(test_session, _group(name), client=None, series_name=topic)
    assert item is not None
    assert (item.season_number, item.episode_number) == expected
