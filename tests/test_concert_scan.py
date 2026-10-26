"""Concert topics ("Concerti · <anime/game>"): every file becomes a concert of that franchise."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.models.media import Franchise, MediaItem, MediaType
from app.services.scanner.concerts import (
    concert_franchise_name,
    concert_title,
    process_concert_group,
)
from app.services.scanner.models import MediaGroup, ScannedFile
from app.services.tmdb import tmdb_client
from app.services.tmdb.models import TMDBResult


def _group(base_name: str, message_id: int) -> MediaGroup:
    return MediaGroup(
        base_name=base_name,
        files=[
            ScannedFile(
                message_id=message_id,
                file_id=f"file{message_id}",
                file_name=base_name,
                file_size=1000,
                base_name=base_name,
                channel_id=-100,
                topic_id=7,
            )
        ],
    )


def _tmdb(title: str) -> TMDBResult:
    return TMDBResult(
        tmdb_id=42,
        title=title,
        overview="An anime",
        poster_path="/p.jpg",
        backdrop_path="/b.jpg",
        release_date="2022-10-28",
        media_type="tv",
    )


@pytest.fixture
def tmdb(mocker):
    search_tv = mocker.patch.object(tmdb_client, "search_tv", new=AsyncMock(return_value=None))
    search_movie = mocker.patch.object(tmdb_client, "search_movie", new=AsyncMock())
    return MagicMock(search_tv=search_tv, search_movie=search_movie)


@pytest.mark.parametrize(
    "topic, name",
    [
        ("Concerti · Arknights", "Arknights"),
        ("concerti - Love Live!", "Love Live!"),
        ("CONCERTI·Genshin Impact", "Genshin Impact"),
        ("Concerti – LiSA", "LiSA"),
        ("Concerti:  Aimer ", "Aimer"),
        ("Concerti • Love Live!", "Love Live!"),
        ("Concerti ・ THE IDOLM@STER", "THE IDOLM@STER"),
        ("Concerti | Genshin Impact", "Genshin Impact"),
        ("Concertino", None),
        ("Arknights", None),
        ("Concerti · ", None),
        (None, None),
    ],
)
def test_concert_franchise_name(topic, name):
    assert concert_franchise_name(topic) == name


@pytest.mark.parametrize(
    "base, expected",
    [
        ("Arknights Ambience Synesthesia 2024.mkv", ("Arknights Ambience Synesthesia 2024", 2024)),
        (
            "Genshin.Concert.2023.Melodies.of.an.Endless.Journey.mkv",
            ("Genshin Concert 2023 Melodies of an Endless Journey", 2023),
        ),
        ("[BD] Aimer Live at Budokan [1080p].mkv", ("Aimer Live at Budokan", None)),
        ("[BD].mkv", ("[BD]", None)),  # only tags: the file name rather than nothing
    ],
)
def test_concert_title(base, expected):
    assert concert_title(base) == expected


async def _concerts(session: AsyncSession) -> list[MediaItem]:
    query = (
        select(MediaItem)
        .options(undefer(MediaItem.setlist), selectinload(MediaItem.parts))
        .order_by(MediaItem.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(query)).scalars())


async def test_concert_topic_creates_one_franchise_and_its_concerts(test_session, tmdb):
    tmdb.search_tv.return_value = _tmdb("Arknights: Prelude to Dawn")

    for message_id in (1, 2):
        group = _group(f"Arknights Ambience Synesthesia 202{message_id + 2}.mkv", message_id)
        assert await process_concert_group(test_session, group, None, "Arknights")

    franchises = (await test_session.execute(select(Franchise))).scalars().all()
    assert [(f.key, f.title, f.tmdb_id, f.poster_path) for f in franchises] == [
        ("arknights", "Arknights", 42, "/p.jpg")
    ]
    concerts = await _concerts(test_session)
    assert [c.media_type for c in concerts] == [MediaType.CONCERT, MediaType.CONCERT]
    assert {c.franchise_id for c in concerts} == {franchises[0].id}
    assert all(c.series_id is None and c.tmdb_id is None for c in concerts)
    assert concerts[1].release_date == date(2024, 1, 1)
    assert len(concerts[0].parts) == 1
    tmdb.search_movie.assert_not_called()


async def test_unrelated_tmdb_result_is_ignored(test_session, tmdb):
    tmdb.search_tv.return_value = _tmdb("Genshin")

    await process_concert_group(test_session, _group("Live 2024.mkv", 1), None, "Honkai Star Rail")

    franchise = (await test_session.execute(select(Franchise))).scalar_one()
    assert (franchise.title, franchise.tmdb_id, franchise.poster_path) == (
        "Honkai Star Rail",
        None,
        None,
    )


@pytest.mark.parametrize(
    "name, tmdb_title",
    [("Fate", "Fated to Love You"), ("♪", "Some Anime"), ("Love", "Lovely Complex")],
)
async def test_tmdb_match_needs_whole_words(test_session, tmdb, name, tmdb_title):
    tmdb.search_tv.return_value = _tmdb(tmdb_title)

    await process_concert_group(test_session, _group("Live 2024.mkv", 1), None, name)

    franchise = (await test_session.execute(select(Franchise))).scalar_one()
    assert franchise.tmdb_id is None


async def test_tmdb_match_accepts_the_same_words_and_more(test_session, tmdb):
    tmdb.search_tv.return_value = _tmdb("Love Live! School Idol Project")

    await process_concert_group(test_session, _group("Live 2024.mkv", 1), None, "Love Live!")

    franchise = (await test_session.execute(select(Franchise))).scalar_one()
    assert franchise.tmdb_id == 42


async def test_rescan_keeps_edits(test_session, tmdb):
    group = _group("Arknights Ambience Synesthesia 2024.mkv", 1)
    concert = await process_concert_group(test_session, group, None, "Arknights")
    assert concert is not None
    concert.title = "Synesthesia"
    concert.setlist = ["Opening"]
    concert.poster_path = "local:mine.png"
    await test_session.commit()

    assert await process_concert_group(test_session, group, None, "Arknights") is None

    concerts = await _concerts(test_session)
    assert [(c.title, c.setlist, c.poster_path) for c in concerts] == [
        ("Synesthesia", ["Opening"], "local:mine.png")
    ]


async def test_renamed_franchise_still_receives_new_concerts(test_session, tmdb):
    first = await process_concert_group(test_session, _group("Live 2023.mkv", 1), None, "Arknights")
    assert first is not None
    franchise = await test_session.get(Franchise, first.franchise_id)
    assert franchise is not None
    franchise.title = "Arknights Live"
    await test_session.commit()

    second = await process_concert_group(
        test_session, _group("Live 2024.mkv", 2), None, "Arknights"
    )

    assert second is not None and second.franchise_id == franchise.id
    count = (await test_session.execute(select(func.count()).select_from(Franchise))).scalar()
    assert count == 1


def _service_with_groups(groups):
    from app.services.scanner.service import ScannerService

    service = ScannerService()
    service._scanner = MagicMock(
        scan_channel=AsyncMock(return_value=[]), group_files=MagicMock(return_value=groups)
    )
    return service


async def test_other_topics_unchanged(mocker):
    group = _group("One.Piece.S01E01.mkv", 1)
    service = _service_with_groups([group])
    series = mocker.patch(
        "app.services.scanner.service.process_group", new=AsyncMock(return_value=MagicMock())
    )
    concerts = mocker.patch(
        "app.services.scanner.service.process_concert_group", new=AsyncMock()
    )
    stats = {"files_found": 0, "topics": 0, "media_created": 0, "errors": []}

    # Topic 99: not the movies topic of the .env
    await service._scan_topic(AsyncMock(), MagicMock(), 1, 99, 10, stats, topic_name="One Piece")

    assert series.await_args.kwargs["series_name"] == "One Piece"
    concerts.assert_not_called()


async def test_concert_topic_goes_to_concerts(mocker):
    group = _group("Arknights Ambience Synesthesia 2024.mkv", 1)
    service = _service_with_groups([group])
    client = MagicMock()
    series = mocker.patch("app.services.scanner.service.process_group", new=AsyncMock())
    concerts = mocker.patch(
        "app.services.scanner.service.process_concert_group",
        new=AsyncMock(return_value=MagicMock()),
    )
    stats = {"files_found": 0, "topics": 0, "media_created": 0, "errors": []}
    session = AsyncMock()

    await service._scan_topic(
        session, client, 1, 99, 10, stats, topic_name="Concerti · Arknights"
    )

    concerts.assert_awaited_once_with(session, group, client, "Arknights")
    series.assert_not_called()
    assert stats["media_created"] == 1
