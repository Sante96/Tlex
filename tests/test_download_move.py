"""A download corrected after its upload: its files move on Telegram, and the old titles
and backup copies go with them."""

import asyncio
from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.models.backup import ArchiveAccount, BackupChannel, BackupMessage
from app.models.download import Download
from app.models.media import Franchise, MediaItem, MediaPart, MediaType, Series
from app.models.user import Profile, User, Watchlist
from app.services.backup import _sync_mixin, backup_service
from app.services.downloads import move, service
from app.services.scanner.service import scanner_service

CHAT = -100


@pytest.fixture(autouse=True)
def setup(monkeypatch, test_session):
    monkeypatch.setattr(get_settings(), "scanner_channel_ids", str(CHAT))
    monkeypatch.setattr(move, "MOVE_RETRY_SECONDS", 0)
    monkeypatch.setattr(move, "async_session_maker", lambda: nullcontext(test_session))
    monkeypatch.setattr(service, "async_session_maker", lambda: nullcontext(test_session))


@pytest.fixture
def scan(mocker):
    return mocker.patch.object(move, "schedule_scan")


def telegram(topics: dict[str, int]) -> MagicMock:
    """A worker client: the group's topics; a copy of message n gets the id n + 800."""

    async def get_forum_topics(chat_id):
        for name, thread in topics.items():
            yield SimpleNamespace(name=name, message_thread_id=thread)

    async def forward_messages(chat_id, from_chat_id, ids, **kwargs):
        return [SimpleNamespace(id=i + 800) for i in ids]

    return MagicMock(
        get_forum_topics=get_forum_topics,
        forward_messages=AsyncMock(side_effect=forward_messages),
        delete_messages=AsyncMock(),
    )


def corrected(*message_ids: list[int]) -> Download:
    """One file per list, uploaded to topic 77 (season 1), then corrected to season 2."""
    file = {"size": 50, "topic": "Show - Stagione 2", "topic_id": 77, "progress": 1.0}
    return Download(
        kind="series",
        name="Show",
        season=2,
        status="library",
        files=[
            {**file, "path": f"S/Episode {n:02}.mkv", "message_ids": ids, "uploaded": True}
            for n, ids in enumerate(message_ids, 1)
        ],
    )


def episode(*message_ids: int, **fields) -> MediaItem:
    item = MediaItem(title="Show", **{"media_type": MediaType.EPISODE, **fields})
    for i, message_id in enumerate(message_ids):
        item.parts.append(
            MediaPart(
                telegram_file_id=f"f{message_id}",
                part_index=i,
                start_byte=0,
                end_byte=50,
                file_size=50,
                channel_id=CHAT,
                message_id=message_id,
            )
        )
    return item


async def archive_account(session) -> int:
    account = ArchiveAccount(phone_number="+390000", session_string="s")
    session.add(account)
    await session.flush()
    return account.id


async def archive_with(session, copies: list[tuple[int, int, bool]]) -> BackupChannel:
    """An archive group (-300) holding these (main id, copy id, pending_delete)."""
    archive = BackupChannel(
        main_channel_id=CHAT,
        backup_channel_id=-300,
        title="A",
        archive_account_id=await archive_account(session),
    )
    session.add(archive)
    await session.flush()
    session.add_all(
        BackupMessage(
            backup_channel_db_id=archive.id,
            main_channel_id=CHAT,
            main_message_id=main_id,
            backup_message_id=copy_id,
            pending_delete=pending,
        )
        for main_id, copy_id, pending in copies
    )
    await session.commit()
    return archive


def daily_run(mocker, account_client, order: list[str]) -> AsyncMock:
    """sync_archive's account client, and its sync_messages (returned) recording its turn."""

    @asynccontextmanager
    async def archive_client(session, account):
        yield account_client

    mocker.patch.object(_sync_mixin, "archive_client", archive_client)
    mocker.patch.object(_sync_mixin, "join_main", new=AsyncMock())
    return mocker.patch.object(
        backup_service,
        "sync_messages",
        new=AsyncMock(side_effect=lambda *a: order.append("sync") or 0),
    )


async def test_a_move_copies_deletes_and_cleans_the_library(test_session, scan):
    download = corrected([100, 101])
    moved, other = episode(100, 101), episode(200)
    test_session.add_all([download, moved, other])
    await test_session.commit()
    client = telegram({"Show - Stagione 1": 77, "Show - Stagione 2": 88})

    await move.move_uploaded(test_session, download, client)

    client.forward_messages.assert_awaited_once_with(
        CHAT, CHAT, [100, 101], message_thread_id=88, send_copy=True
    )
    client.delete_messages.assert_awaited_once_with(CHAT, [100, 101])
    left = (await test_session.scalars(select(MediaItem.id))).all()
    assert left == [other.id]
    assert (await test_session.scalars(select(MediaPart.message_id))).all() == [200]
    assert download.files[0]["message_ids"] == [900, 901]
    assert (download.files[0]["topic_id"], download.files[0]["stale_ids"]) == (88, [])
    scan.assert_called_once_with(download.id, [88], [], [])

    # Nothing changed since: a second move touches nothing
    client.forward_messages.reset_mock()
    client.delete_messages.reset_mock()
    await move.move_uploaded(test_session, download, client)
    client.forward_messages.assert_not_awaited()
    client.delete_messages.assert_not_awaited()


async def test_a_move_clears_the_old_backup_copies(test_session, scan):
    workers = BackupChannel(main_channel_id=CHAT, backup_channel_id=-200, title="B")
    download = corrected([100])
    test_session.add_all([workers, download])
    await test_session.flush()
    test_session.add(
        BackupMessage(
            backup_channel_db_id=workers.id,
            main_channel_id=CHAT,
            main_message_id=100,
            backup_message_id=500,
        )
    )
    await archive_with(test_session, [(100, 700, False)])
    client = telegram({"Show - Stagione 2": 88})

    await move.move_uploaded(test_session, download, client)

    assert client.delete_messages.await_args_list == [call(CHAT, [100]), call(-200, [500])]
    rows = (await test_session.scalars(select(BackupMessage))).all()
    assert [(r.backup_message_id, r.pending_delete) for r in rows] == [(700, True)]


async def test_a_move_failed_halfway_is_finished_by_the_next_one(test_session, scan):
    download = corrected([100], [200])
    test_session.add(download)
    await test_session.commit()
    client = telegram({"Show - Stagione 2": 88})
    client.delete_messages.side_effect = [None, RuntimeError("Telegram is down")]

    with pytest.raises(RuntimeError):
        await move.move_uploaded(test_session, download, client)

    first, second = download.files
    assert (first["topic_id"], first["message_ids"], first["stale_ids"]) == (88, [900], [])
    # Copied, and recorded as such: its originals wait in stale_ids
    assert (second["topic_id"], second["message_ids"], second["stale_ids"]) == (88, [1000], [200])
    scan.assert_called_once_with(download.id, [88], [], [])

    client.forward_messages.reset_mock()
    client.delete_messages.reset_mock(side_effect=True)
    await move.move_uploaded(test_session, download, client)

    client.forward_messages.assert_not_awaited()
    client.delete_messages.assert_awaited_once_with(CHAT, [200])
    assert download.files[1]["stale_ids"] == []


async def test_a_season_fix_keeps_its_series(test_session, mocker):
    # On: the watchlist row goes with its series, as in PostgreSQL
    await test_session.execute(text("PRAGMA foreign_keys=ON"))
    user = User(email="u@example.com", password_hash="h", profiles=[Profile(name="main")])
    show = Series(title="Show", tmdb_id=1)
    download = corrected([100])
    test_session.add_all([user, show, download, episode(100, series=show)])
    await test_session.flush()
    test_session.add(Watchlist(user_id=user.id, profile_id=user.profiles[0].id, series_id=show.id))
    await test_session.commit()
    show_id = show.id

    async def scan_all_channels(session, topic_id):
        # The copy's TMDB match is the same series: the scanner files it there
        session.add(episode(900, series_id=show_id))
        await session.commit()
        return {}

    mocker.patch.object(scanner_service, "scan_all_channels", side_effect=scan_all_channels)

    await move.move_uploaded(test_session, download, telegram({"Show - Stagione 2": 88}))
    await asyncio.gather(*list(service._tasks))

    assert (await test_session.scalars(select(Series.id))).all() == [show_id]
    assert (await test_session.scalars(select(Watchlist.series_id))).all() == [show_id]


async def test_a_title_a_correction_emptied_goes_after_the_scan(test_session, mocker):
    wrong, kept = Series(title="Wrong"), Series(title="Kept")
    franchise = Franchise(key="wrong", title="Wrong")
    download = corrected([100], [200], [300])
    test_session.add_all(
        [
            download,
            episode(100, series=wrong),
            episode(200, series=kept),
            episode(400, series=kept),  # not this download's: "Kept" is never deleted
            episode(300, media_type=MediaType.CONCERT, franchise=franchise),
        ]
    )
    await test_session.commit()
    scanner = mocker.patch.object(scanner_service, "scan_all_channels", return_value={})

    await move.move_uploaded(test_session, download, telegram({"Show - Stagione 2": 88}))

    titles = select(Series.title).order_by(Series.title)
    assert (await test_session.scalars(titles)).all() == ["Kept", "Wrong"]  # not before it
    await asyncio.gather(*list(service._tasks))
    scanner.assert_awaited_once()
    assert (await test_session.scalars(titles)).all() == ["Kept"]
    assert (await test_session.scalars(select(Franchise.id))).all() == []


async def test_no_title_is_pruned_without_its_scan(test_session, mocker, monkeypatch):
    monkeypatch.setattr(service, "SCAN_RETRY_SECONDS", 0)
    monkeypatch.setattr(service, "SCAN_RETRIES", 2)
    wrong = Series(title="Wrong")
    download = corrected([100])
    test_session.add_all([download, episode(100, series=wrong)])
    await test_session.commit()
    busy = {"error": "Scan already in progress"}
    scanner = mocker.patch.object(scanner_service, "scan_all_channels", return_value=busy)

    await move.move_uploaded(test_session, download, telegram({"Show - Stagione 2": 88}))
    await asyncio.gather(*list(service._tasks))

    # The scan that would have put the copy back in it never ran: kept
    assert scanner.await_count == 2
    assert (await test_session.scalars(select(Series.title))).all() == ["Wrong"]


async def test_the_archive_deletes_its_pending_copies_at_its_daily_run(test_session, mocker):
    archive = await archive_with(test_session, [(100, 700, True), (5, 505, False)])
    order: list[str] = []
    account_client = MagicMock(
        delete_messages=AsyncMock(side_effect=lambda *a: order.append("delete"))
    )
    daily_run(mocker, account_client, order)

    await backup_service.sync_archive(test_session, archive)

    account_client.delete_messages.assert_awaited_once_with(-300, [700])
    assert order == ["delete", "sync"]
    left = (await test_session.scalars(select(BackupMessage.backup_message_id))).all()
    assert left == [505]


async def test_the_archive_deletes_by_hundreds_and_a_failure_skips_its_chunk(test_session, mocker):
    archive = await archive_with(test_session, [(i, 1000 + i, True) for i in range(150)])
    account_client = MagicMock(delete_messages=AsyncMock(side_effect=[RuntimeError("flood"), None]))
    sync = daily_run(mocker, account_client, [])

    await backup_service.sync_archive(test_session, archive)

    sizes = [len(c.args[1]) for c in account_client.delete_messages.await_args_list]
    assert sizes == [100, 50]
    sync.assert_awaited_once()
    left = (await test_session.scalars(select(BackupMessage.pending_delete))).all()
    assert left == [True] * 100  # the failed chunk waits for the next run


async def test_a_correction_answers_at_once_and_moves_in_the_background(
    client: AsyncClient, auth_headers: dict, test_session, mocker
):
    schedule = mocker.patch.object(move, "schedule_move")
    download = corrected([100])
    download.season, download.files = 1, [{**download.files[0], "topic": "Show - Stagione 1"}]
    test_session.add(download)
    await test_session.commit()

    body = {"kind": "series", "name": "Show", "season": 2}
    r = await client.patch(f"/api/v1/downloads/{download.id}", json=body, headers=auth_headers)

    assert r.status_code == 200, r.text
    assert r.json()["files"][0]["topic"] == "Show - Stagione 2"
    schedule.assert_called_once_with(download.id)


async def test_a_move_without_a_worker_retries_then_shows_an_error(test_session, mocker, scan):
    download = corrected([100])
    test_session.add(download)
    await test_session.commit()
    best = mocker.patch.object(worker_manager, "get_best_worker", new=AsyncMock(return_value=None))

    move.schedule_move(download.id)
    await asyncio.gather(*move._moves.values())

    assert best.await_count == move.MOVE_RETRIES
    assert download.error == f"{move.MOVE_FAILED}: {move.NO_WORKER}"

    # A worker again, and the move asked again while it runs: it runs once more after,
    # and finds nothing left to do
    client = telegram({"Show - Stagione 2": 88})

    async def a_worker(session):
        if best.await_count == 1:
            move.schedule_move(download.id)  # asked again while this move runs
        return MagicMock(), client

    best.reset_mock()
    best.side_effect = a_worker
    move.schedule_move(download.id)
    await asyncio.gather(*move._moves.values())

    assert best.await_count == 2
    client.forward_messages.assert_awaited_once()
    assert download.files[0]["message_ids"] == [900]
    assert download.error is None
