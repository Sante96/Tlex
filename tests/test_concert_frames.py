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
        backdrop_path="local:mine.png",
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


async def test_a_pass_asked_for_while_running_looks_again(test_session, mocker):
    first = MediaItem(title="First", media_type=MediaType.CONCERT, duration_seconds=60)
    test_session.add(first)
    await test_session.commit()
    added: list[MediaItem] = []

    async def grab_and_meanwhile_scan(media_id, at_seconds):
        if not added:  # a scan adds a concert while this pass is busy, and asks for frames
            added.append(MediaItem(title="Late", media_type=MediaType.CONCERT, duration_seconds=60))
            test_session.add(added[0])
            await test_session.commit()
            assert await concert_frames.backfill_concert_frames() == 0
        return JPEG

    mocker.patch.object(concert_frames, "grab_frame", side_effect=grab_and_meanwhile_scan)

    assert await concert_frames.backfill_concert_frames() == 2
    assert LOCAL_JPG.match((await _items(test_session))["Late"].poster_path or "")


async def test_a_missing_backdrop_is_filled_and_a_chosen_poster_kept(test_session, mocker):
    test_session.add(
        MediaItem(
            title="Chosen",
            media_type=MediaType.CONCERT,
            duration_seconds=600,
            poster_path="local:mine.png",
        )
    )
    await test_session.commit()
    mocker.patch.object(concert_frames, "grab_frame", return_value=JPEG)

    assert await concert_frames.backfill_concert_frames() == 1

    chosen = (await _items(test_session))["Chosen"]
    assert chosen.poster_path == "local:mine.png"
    assert LOCAL_JPG.match(chosen.backdrop_path or "")


async def test_unknown_duration_grabs_at_a_fixed_offset(test_session, mocker):
    test_session.add(MediaItem(title="Bare", media_type=MediaType.CONCERT))
    await test_session.commit()
    grab = mocker.patch.object(concert_frames, "grab_frame", return_value=JPEG)

    await concert_frames.backfill_concert_frames()

    grab.assert_awaited_once()
    assert grab.await_args.args[1] == concert_frames.FALLBACK_AT


def _runs(mocker, transfer: str):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        out = (transfer + "\n").encode() if "ffprobe" in cmd[0] else JPEG
        return mocker.Mock(returncode=0, stdout=out, stderr=b"")

    mocker.patch.object(concert_frames.subprocess, "run", side_effect=run)
    mocker.patch.object(concert_frames, "find_ffprobe", return_value="ffprobe")
    mocker.patch.object(concert_frames, "find_ffmpeg", return_value="ffmpeg")
    return calls


@pytest.mark.parametrize("transfer, tonemapped", [("smpte2084", True), ("bt709", False)])
async def test_hdr_frames_are_tone_mapped(mocker, transfer, tonemapped):
    calls = _runs(mocker, transfer)

    assert await concert_frames.grab_frame(7, 100.0) == JPEG

    ffmpeg = calls[-1]
    filters = ffmpeg[ffmpeg.index("-vf") + 1]
    assert ("tonemap" in filters) is tonemapped
    assert filters.endswith("scale=1280:-2") or "scale=1280:-2" in filters
