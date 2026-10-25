"""BackupService sync: sync_all gives its pool client back (it used to leak one per run),
and a failed forward batch doesn't lose the batches already on Telegram."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import func, select

from app.models.backup import BackupChannel, BackupMessage
from app.services.backup import _sync_mixin, backup_service


async def test_sync_all_releases_client_even_when_a_backup_fails(mocker):
    client = MagicMock()
    session = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [MagicMock(id=1)]
    maker = mocker.patch("app.services.backup._sync_mixin.async_session_maker")
    maker.return_value.__aenter__.return_value = session
    mocker.patch(
        "app.core.worker_manager.worker_manager.get_available_clients",
        new=AsyncMock(return_value=[client]),
    )
    release = mocker.patch("app.core.worker_manager.worker_manager.release_clients")
    mocker.patch.object(backup_service, "check_health", new=AsyncMock(side_effect=RuntimeError))

    result = await backup_service.sync_all()

    assert result["errors"]
    release.assert_called_once_with([client])


async def test_sync_all_without_backups_takes_no_client(mocker):
    session = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    maker = mocker.patch("app.services.backup._sync_mixin.async_session_maker")
    maker.return_value.__aenter__.return_value = session
    acquire = mocker.patch(
        "app.core.worker_manager.worker_manager.get_available_clients", new=AsyncMock()
    )

    await backup_service.sync_all()

    acquire.assert_not_called()


class FakeClient:
    """One topic with 250 media messages; the second forward call fails."""

    def __init__(self):
        self.calls = 0
        self.forwarded: list[int] = []

    async def get_forum_topics(self, chat_id):
        return
        yield

    async def get_discussion_replies(self, chat_id, topic_id, limit):
        for i in range(1, 251):
            yield SimpleNamespace(id=i, document=True, video=None)

    async def resolve_peer(self, peer):
        return SimpleNamespace()

    async def invoke(self, query):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("timeout on the second batch")
        self.forwarded.extend(query.id)
        return SimpleNamespace(
            updates=[SimpleNamespace(message=SimpleNamespace(id=10_000 + i)) for i in query.id]
        )


async def test_failed_batch_keeps_the_others(test_session, mocker):
    mocker.patch.object(_sync_mixin, "asyncio", SimpleNamespace(sleep=AsyncMock()))
    backup = BackupChannel(
        main_channel_id=-1001,
        backup_channel_id=-1002,
        title="t",
        topic_map={"5": {"backup_id": 7, "name": "x"}},
    )
    test_session.add(backup)
    await test_session.commit()
    client: Any = FakeClient()  # stands in for a Pyrogram Client

    assert await backup_service.sync_messages(test_session, client, backup) == 150
    recorded = await test_session.scalar(select(func.count()).select_from(BackupMessage))
    assert recorded == len(client.forwarded) == 150  # batches 1 and 3

    # The next run forwards only the batch that failed
    client.forwarded.clear()
    assert await backup_service.sync_messages(test_session, client, backup) == 100
    assert client.forwarded == list(range(101, 201))
