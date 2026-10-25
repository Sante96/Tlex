"""Chapters: read by ffprobe at scan time, returned with the details, filled in for old titles."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.models.media import MediaItem, MediaType
from app.services.ffprobe import FFProbeService, ProbeResult


def test_ffprobe_reads_chapters_and_drops_generic_names():
    data = {
        "format": {"duration": "300.0"},
        "streams": [],
        "chapters": [
            {"start_time": "0.000000", "end_time": "139.291667", "tags": {"title": "Chapter 01"}},
            {"start_time": "139.291667", "end_time": "200.5", "tags": {"title": "Opening"}},
            {"start_time": "200.5", "end_time": "250.0", "tags": {"title": "00:03:20.500"}},
            {"start_time": "250.0", "end_time": "300.0"},
        ],
    }
    chapters = FFProbeService()._parse_probe_data(data).chapters

    assert chapters == [
        {"start": 0.0, "end": 139.292, "title": None},
        {"start": 139.292, "end": 200.5, "title": "Opening"},
        {"start": 200.5, "end": 250.0, "title": None},
        {"start": 250.0, "end": 300.0, "title": None},
    ]


async def test_details_carry_the_chapters(
    client: AsyncClient, auth_headers: dict, test_session: AsyncSession
):
    concert = MediaItem(
        title="Live",
        media_type=MediaType.MOVIE,
        chapters=[
            {"start": 0.0, "end": 60.0, "title": None},
            {"start": 60.0, "end": 120.0, "title": "Encore"},
        ],
    )
    plain = MediaItem(title="Film", media_type=MediaType.MOVIE)
    test_session.add_all([concert, plain])
    await test_session.commit()

    detail = (await client.get(f"/api/v1/media/{concert.id}", headers=auth_headers)).json()
    assert detail["chapters"] == [
        {"start": 0.0, "end": 60.0, "title": None},
        {"start": 60.0, "end": 120.0, "title": "Encore"},
    ]
    # Never probed: no chapters, not an empty list
    assert (await client.get(f"/api/v1/media/{plain.id}", headers=auth_headers)).json()[
        "chapters"
    ] is None


async def test_backfill_reads_only_the_titles_never_probed(test_session: AsyncSession, mocker):
    from app.services import chapters as chapters_service

    old = MediaItem(title="Old", media_type=MediaType.MOVIE)
    done = MediaItem(title="Done", media_type=MediaType.MOVIE, chapters=[])
    broken = MediaItem(title="Broken", media_type=MediaType.MOVIE)
    test_session.add_all([old, done, broken])
    await test_session.commit()

    found = [
        {"start": 0.0, "end": 10.0, "title": None},
        {"start": 10.0, "end": 20.0, "title": None},
    ]

    async def probe(session, media_id):
        if media_id == broken.id:
            return None  # Telegram failed: try again at the next start
        return ProbeResult(duration_seconds=20, streams=[], chapters=found)

    probe_head = mocker.patch.object(chapters_service, "probe_head", side_effect=probe)
    mocker.patch.object(chapters_service, "PAUSE_SECONDS", 0)
    mocker.patch.object(chapters_service, "async_session_maker", lambda: _same(test_session))

    assert await chapters_service.backfill_chapters() == 1

    probed = sorted(call.args[1] for call in probe_head.call_args_list)
    assert probed == sorted([old.id, broken.id])
    # chapters is deferred: ask for it, and over the objects already in the session
    query = (
        select(MediaItem)
        .options(undefer(MediaItem.chapters))
        .execution_options(populate_existing=True)
    )
    rows = {m.title: m.chapters for m in (await test_session.execute(query)).scalars()}
    assert rows == {"Old": found, "Done": [], "Broken": None}


class _same:
    """The test's session as an async context manager (the service opens its own)."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False
