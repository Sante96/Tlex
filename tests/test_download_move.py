"""A download corrected after its upload: its files move on Telegram, and the old titles
and backup copies go with them."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.models.backup import ArchiveAccount, BackupChannel, BackupMessage
from app.models.download import Download
from app.models.media import MediaItem, MediaPart, MediaType
from app.services.backup import _sync_mixin, backup_service
from app.services.downloads import move

CHAT = -100


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(get_settings(), "scanner_channel_ids", str(CHAT))


@pytest.fixture
def scan(mocker):
    return mocker.patch.object(move, "schedule_scan")


def telegram(topics: dict[str, int], copies: list[int]) -> MagicMock:
    """A worker client: the group's topics, and the ids its copies get."""

    async def get_forum_topics(chat_id):
        for name, thread in topics.items():
            yield SimpleNamespace(name=name, message_thread_id=thread)

    return MagicMock(
        get_forum_topics=get_forum_topics,
        forward_messages=AsyncMock(return_value=[SimpleNamespace(id=i) for i in copies]),
        delete_messages=AsyncMock(),
    )


def corrected(message_ids: list[int]) -> Download:
    """Uploaded to topic 77 (season 1), then corrected to season 2."""
    file = {"path": "S/Episode 01.mkv", "size": 50, "topic": "Show - Stagione 2", "topic_id": 77}
    return Download(
        kind="series",
        name="Show",
        season=2,
        status="library",
        files=[{**file, "progress": 1.0, "message_ids": message_ids, "uploaded": True}],
    )


async def archive_account(session) -> int:
    account = ArchiveAccount(phone_number="+390000", session_string="s")
    session.add(account)
    await session.flush()
    return account.id


def episode(*message_ids: int) -> MediaItem:
    item = MediaItem(title="Show", media_type=MediaType.EPISODE)
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


async def test_a_move_copies_deletes_and_cleans_the_library(test_session, scan):
    download = corrected([100, 101])
    moved, other = episode(100, 101), episode(200)
    test_session.add_all([download, moved, other])
    await test_session.commit()
    client = telegram({"Show - Stagione 1": 77, "Show - Stagione 2": 88}, [900, 901])

    await move.move_uploaded(test_session, download, client)

    client.forward_messages.assert_awaited_once_with(
        CHAT, CHAT, [100, 101], message_thread_id=88, send_copy=True
    )
    client.delete_messages.assert_awaited_once_with(CHAT, [100, 101])
    left = (await test_session.scalars(select(MediaItem.id))).all()
    assert left == [other.id]
    assert (await test_session.scalars(select(MediaPart.message_id))).all() == [200]
    assert download.files[0]["message_ids"] == [900, 901]
    assert download.files[0]["topic_id"] == 88
    scan.assert_called_once_with(download.id, [88])


async def test_a_move_clears_the_old_backup_copies(test_session, scan):
    account = await archive_account(test_session)
    workers = BackupChannel(main_channel_id=CHAT, backup_channel_id=-200, title="B")
    archive = BackupChannel(
        main_channel_id=CHAT, backup_channel_id=-300, title="A", archive_account_id=account
    )
    download = corrected([100])
    test_session.add_all([workers, archive, download])
    await test_session.flush()
    for group, copy_id in ((workers, 500), (archive, 700)):
        test_session.add(
            BackupMessage(
                backup_channel_db_id=group.id,
                main_channel_id=CHAT,
                main_message_id=100,
                backup_message_id=copy_id,
            )
        )
    await test_session.commit()
    client = telegram({"Show - Stagione 2": 88}, [900])

    await move.move_uploaded(test_session, download, client)

    assert client.delete_messages.await_args_list[-1].args == (-200, [500])
    rows = (await test_session.scalars(select(BackupMessage))).all()
    assert [(r.backup_message_id, r.pending_delete) for r in rows] == [(700, True)]


async def test_the_archive_deletes_its_pending_copies_at_its_daily_run(test_session, mocker):
    archive = BackupChannel(
        main_channel_id=CHAT,
        backup_channel_id=-300,
        title="A",
        archive_account_id=await archive_account(test_session),
    )
    test_session.add(archive)
    await test_session.flush()
    for main_id, copy_id, pending in ((100, 700, True), (5, 505, False)):
        test_session.add(
            BackupMessage(
                backup_channel_db_id=archive.id,
                main_channel_id=CHAT,
                main_message_id=main_id,
                backup_message_id=copy_id,
                pending_delete=pending,
            )
        )
    await test_session.commit()
    order: list[str] = []
    account_client = MagicMock(
        delete_messages=AsyncMock(side_effect=lambda *a: order.append("delete"))
    )

    @asynccontextmanager
    async def archive_client(session, account):
        yield account_client

    mocker.patch.object(_sync_mixin, "archive_client", archive_client)
    mocker.patch.object(_sync_mixin, "join_main", new=AsyncMock())
    mocker.patch.object(
        backup_service,
        "sync_messages",
        new=AsyncMock(side_effect=lambda *a: order.append("sync") or 0),
    )

    await backup_service.sync_archive(test_session, archive)

    account_client.delete_messages.assert_awaited_once_with(-300, [700])
    assert order == ["delete", "sync"]
    left = (await test_session.scalars(select(BackupMessage.backup_message_id))).all()
    assert left == [505]


async def test_a_correction_moves_what_is_uploaded(
    client: AsyncClient, auth_headers: dict, test_session, mocker, scan
):
    download = corrected([100])
    download.season, download.files = 1, [{**download.files[0], "topic": "Show - Stagione 1"}]
    test_session.add(download)
    await test_session.commit()
    worker_client = telegram({"Show - Stagione 1": 77}, [900])
    worker_client.create_forum_topic = AsyncMock(return_value=SimpleNamespace(message_thread_id=88))
    best = mocker.patch.object(worker_manager, "get_best_worker", new=AsyncMock(return_value=None))
    body = {"kind": "series", "name": "Show", "season": 2}

    r = await client.patch(f"/api/v1/downloads/{download.id}", json=body, headers=auth_headers)
    assert r.status_code == 503
    worker_client.forward_messages.assert_not_awaited()

    best.return_value = (MagicMock(), worker_client)
    r = await client.patch(f"/api/v1/downloads/{download.id}", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    worker_client.create_forum_topic.assert_awaited_once_with(CHAT, "Show - Stagione 2")
    file = r.json()["files"][0]
    assert (file["topic"], file["topic_id"], file["message_ids"]) == (
        "Show - Stagione 2",
        88,
        [900],
    )
    scan.assert_called_once_with(download.id, [88])
