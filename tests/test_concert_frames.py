"""A concert without an image gets a frame of its own video."""

import asyncio
import re

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import MediaItem, MediaType
from app.services import concert_frames, images

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
LOCAL_JPG = re.compile(r"^local:[0-9a-f]{32}\.jpg$")


class _same:
    """The test's session as an async context manager (the service opens its own)."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch, test_session):
    monkeypatch.setattr(images, "IMAGES_DIR", tmp_path)
    monkeypatch.setattr(concert_frames, "PAUSE_SECONDS", 0)
    monkeypatch.setattr(concert_frames, "async_session_maker", lambda: _same(test_session))


async def _items(session: AsyncSession) -> dict[str, MediaItem]:
    query = select(MediaItem).execution_options(populate_existing=True)
    return {m.title: m for m in (await session.execute(query)).scalars()}


async def test_frames_fill_only_concerts_without_image(test_session, mocker):
    bare = MediaItem(title="Bare", media_type=MediaType.CONCERT, duration_seconds=5940)
    chosen = MediaItem(
        title="Chosen",
        media_type=MediaType.CONCERT,
        duration_seconds=600,
        poster_path="local:mine.png",
    )
    film = MediaItem(title="Film", media_type=MediaType.MOVIE, duration_seconds=600)
    test_session.add_all([bare, chosen, film])
    await test_session.commit()
    grab = mocker.patch.object(concert_frames, "grab_frame", return_value=JPEG)

    assert await concert_frames.backfill_concert_frames() == 1

    grab.assert_awaited_once_with(bare.id, 2970.0)
    items = await _items(test_session)
    assert LOCAL_JPG.match(items["Bare"].poster_path or "")
    assert items["Bare"].backdrop_path == items["Bare"].poster_path
    assert items["Chosen"].poster_path == "local:mine.png"
    assert items["Film"].poster_path is None


async def test_failed_grab_leaves_concert_without_image(test_session, mocker):
    test_session.add(MediaItem(title="Bare", media_type=MediaType.CONCERT, duration_seconds=60))
    await test_session.commit()
    mocker.patch.object(concert_frames, "grab_frame", return_value=None)

    assert await concert_frames.backfill_concert_frames() == 0

    assert (await _items(test_session))["Bare"].poster_path is None


async def test_frames_run_once_at_a_time(test_session, mocker):
    test_session.add(MediaItem(title="Bare", media_type=MediaType.CONCERT, duration_seconds=60))
    await test_session.commit()

    async def slow_grab(media_id, at_seconds):
        await asyncio.sleep(0.05)
        return JPEG

    grab = mocker.patch.object(concert_frames, "grab_frame", side_effect=slow_grab)

    done = await asyncio.gather(
        concert_frames.backfill_concert_frames(), concert_frames.backfill_concert_frames()
    )

    assert sorted(done) == [0, 1]
    assert grab.await_count == 1
