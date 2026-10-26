"""Archive groups: a backup no worker is in, owned and filled by an account that never
streams, so a ban of the workers can't take it down with the other two groups."""

from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.worker_manager import worker_manager
from app.models.backup import ArchiveAccount, BackupChannel, BackupMessage
from app.services.backup import _failover_mixin, _sync_mixin, archive, backup_service


def fake_account(*chat_ids: int) -> MagicMock:
    """An archive account's client, a member of these chats."""

    async def get_dialogs():
        for chat_id in chat_ids:
            yield SimpleNamespace(chat=SimpleNamespace(id=chat_id))

    return MagicMock(get_dialogs=get_dialogs, join_chat=AsyncMock())


def opened(client):
    """archive_client, for an account whose client is this one."""

    @asynccontextmanager
    async def archive_client(session, account):
        yield client

    return archive_client


@pytest.fixture
async def account(test_session):
    account = ArchiveAccount(phone_number="+390000", session_string="s")
    test_session.add(account)
    await test_session.commit()
    return account


def link(url: str) -> SimpleNamespace:
    return SimpleNamespace(invite_link=url)


# -- the account joins the main group through a worker's one-use link --


async def test_the_archive_account_joins_the_main_group_with_a_worker_link():
    from pyrogram.errors import ChatAdminRequired

    # The first worker account isn't an admin of the main group: the next one invites
    not_admin = MagicMock(create_chat_invite_link=AsyncMock(side_effect=ChatAdminRequired()))
    admin = MagicMock(create_chat_invite_link=AsyncMock(return_value=link("https://t.me/+a")))
    account_client = fake_account(-300)  # only its own group

    await archive.join_main([not_admin, admin], account_client, -100)

    admin.create_chat_invite_link.assert_awaited_once_with(-100, member_limit=1)
    account_client.join_chat.assert_awaited_once_with("https://t.me/+a")


async def test_no_worker_allowed_to_invite_is_an_error():
    from pyrogram.errors import ChatAdminRequired

    not_admin = MagicMock(create_chat_invite_link=AsyncMock(side_effect=ChatAdminRequired()))

    with pytest.raises(RuntimeError, match="No worker account could invite"):
        await archive.join_main([not_admin], fake_account(-300), -100)


async def test_a_member_of_the_main_group_needs_no_link():
    worker = MagicMock(create_chat_invite_link=AsyncMock())
    account_client = fake_account(-300, -100)

    await archive.join_main([worker], account_client, -100)

    worker.create_chat_invite_link.assert_not_awaited()
    account_client.join_chat.assert_not_awaited()


# -- one archive per main channel, beside the backup --


async def test_an_archive_sits_beside_the_backup(test_session, account, mocker):
    mocker.patch.object(backup_service, "_create_megagroup", new=AsyncMock(side_effect=[-300, -400, -500]))
    mocker.patch.object(backup_service, "_mirror_topics", new=AsyncMock(return_value={}))
    test_session.add(BackupChannel(main_channel_id=-100, backup_channel_id=-200, title="B"))
    await test_session.commit()

    made = await backup_service.create_backup_channel(
        test_session, MagicMock(), -100, "A", archive_account_id=account.id
    )

    assert (made.backup_channel_id, made.archive_account_id) == (-300, account.id)
    with pytest.raises(ValueError):
        await backup_service.create_backup_channel(test_session, MagicMock(), -100, "B2")
    with pytest.raises(ValueError):
        await backup_service.create_backup_channel(
            test_session, MagicMock(), -100, "A2", archive_account_id=account.id
        )


# -- filled once a day by its own account, never health-checked nor promoted --


async def test_the_archive_is_filled_by_its_account_once_a_day(test_session, account, mocker):
    group = BackupChannel(
        main_channel_id=-100, backup_channel_id=-300, title="A", archive_account_id=account.id
    )
    test_session.add(group)
    await test_session.commit()
    maker = mocker.patch.object(_sync_mixin, "async_session_maker")
    maker.return_value.__aenter__.return_value = test_session
    mocker.patch.object(worker_manager, "get_available_clients", new=AsyncMock(return_value=[MagicMock()]))
    mocker.patch.object(worker_manager, "release_clients")
    workers = [MagicMock()]
    mocker.patch.object(worker_manager, "primary_clients", return_value=workers)
    account_client = MagicMock()
    mocker.patch.object(_sync_mixin, "archive_client", opened(account_client))
    join = mocker.patch.object(_sync_mixin, "join_main", new=AsyncMock())
    health = mocker.patch.object(backup_service, "check_health", new=AsyncMock())
    sync = mocker.patch.object(backup_service, "sync_messages", new=AsyncMock(return_value=3))

    assert (await backup_service.sync_all())["synced"] == 3
    join.assert_awaited_once_with(workers, account_client, -100)
    assert sync.await_args.args[1] is account_client
    health.assert_not_awaited()

    group.last_sync_at = datetime.utcnow()  # what sync_messages records
    await test_session.commit()
    sync.reset_mock()
    await backup_service.sync_all()
    sync.assert_not_awaited()


async def test_streams_never_fall_back_on_the_archive(test_session, account, mocker):
    group = BackupChannel(
        main_channel_id=-100, backup_channel_id=-300, title="A", archive_account_id=account.id
    )
    test_session.add(group)
    await test_session.flush()
    test_session.add(
        BackupMessage(
            backup_channel_db_id=group.id, main_channel_id=-100, main_message_id=5,
            backup_message_id=505,
        )
    )
    await test_session.commit()
    maker = mocker.patch.object(_failover_mixin, "async_session_maker")
    maker.return_value.__aenter__.return_value = test_session

    # No worker is in the archive group: it can't serve a stream
    assert await backup_service.get_fallback_location(-100, 5) is None


# -- the backup's promotion moves the archive to the new main group --


async def test_the_archive_follows_a_promoted_backup(test_session, account, mocker):
    backup = BackupChannel(
        main_channel_id=-100, backup_channel_id=-200, title="B",
        topic_map={"7": {"backup_id": 70, "name": "Film"}},
    )
    group = BackupChannel(
        main_channel_id=-100, backup_channel_id=-300, title="A", archive_account_id=account.id,
        topic_map={"7": {"backup_id": 700, "name": "Film"}},
    )
    test_session.add_all([backup, group])
    await test_session.flush()

    def copy(of: BackupChannel, main_id: int, copy_id: int) -> BackupMessage:
        return BackupMessage(
            backup_channel_db_id=of.id, main_channel_id=-100, main_message_id=main_id,
            backup_message_id=copy_id,
        )

    test_session.add_all([copy(backup, 5, 55), copy(backup, 6, 66), copy(group, 5, 505), copy(group, 8, 808)])
    await test_session.commit()
    mocker.patch.object(backup_service, "create_backup_channel", new=AsyncMock(return_value=MagicMock()))

    await backup_service.promote_to_main(test_session, MagicMock(), backup)

    assert group.main_channel_id == -200
    assert group.topic_map == {"70": {"backup_id": 700, "name": "Film"}}
    rows = (
        await test_session.execute(
            select(BackupMessage.main_channel_id, BackupMessage.main_message_id, BackupMessage.backup_message_id)
            .where(BackupMessage.backup_channel_db_id == group.id)
        )
    ).all()
    # 8 never reached the backup, so it isn't in the new main: its copy maps to nothing,
    # and an id of the old group must not shadow a message of the new one
    assert rows == [(-200, 55, 505)]
    assert group.is_active and not group.is_promoted


# -- promoting the archive: the workers come in first --


async def test_promoting_the_archive_lets_the_workers_in_first(test_session, account, mocker):
    group = BackupChannel(
        main_channel_id=-100, backup_channel_id=-300, title="A", archive_account_id=account.id
    )
    test_session.add(group)
    await test_session.commit()
    workers = [MagicMock(join_chat=AsyncMock()), MagicMock(join_chat=AsyncMock())]
    mocker.patch.object(worker_manager, "primary_clients", return_value=workers)
    account_client = fake_account(-300)
    account_client.create_chat_invite_link = AsyncMock(side_effect=[link("l1"), link("l2")])
    members_read = []

    async def get_chat_members(chat_id):
        members_read.append(chat_id)
        for worker in workers:
            yield SimpleNamespace(user=worker.me)

    async def promote_chat_member(chat_id, user_id, privileges):
        # The account knows a user's access hash only once it has read them
        assert members_read == [-300]

    account_client.get_chat_members = get_chat_members
    account_client.promote_chat_member = AsyncMock(side_effect=promote_chat_member)
    mocker.patch.object(_failover_mixin, "archive_client", opened(account_client))
    promote = mocker.patch.object(backup_service, "promote_to_main", new=AsyncMock())

    await backup_service.promote_archive(test_session, group)

    workers[0].join_chat.assert_awaited_once_with("l1")
    workers[1].join_chat.assert_awaited_once_with("l2")
    account_client.create_chat_invite_link.assert_awaited_with(-300, member_limit=1)
    # Admins, as in the main group: invite links for the next archive, topics
    promoted = [c.args[:2] for c in account_client.promote_chat_member.await_args_list]
    assert promoted == [(-300, workers[0].me.id), (-300, workers[1].me.id)]
    promote.assert_awaited_once_with(test_session, workers[0], group)


async def test_promoting_the_archive_retires_the_lost_backup(test_session, account, mocker):
    # The workers' backup of the lost main group would otherwise keep failing its health
    # check and get promoted on its own, onto a group that is lost too
    backup = BackupChannel(main_channel_id=-100, backup_channel_id=-200, title="B")
    group = BackupChannel(
        main_channel_id=-100, backup_channel_id=-300, title="A", archive_account_id=account.id
    )
    test_session.add_all([backup, group])
    await test_session.commit()
    mocker.patch.object(backup_service, "create_backup_channel", new=AsyncMock(return_value=MagicMock()))

    await backup_service.promote_to_main(test_session, MagicMock(), group)

    assert not backup.is_active and not backup.is_promoted
    assert group.is_promoted


async def test_a_failed_sync_doesnt_skip_the_next_group(test_session, account, mocker):
    # A failed forward batch rolls the session back, which expires every object loaded
    # in it: the next group's attributes then can't be read in async code
    first = BackupChannel(main_channel_id=-100, backup_channel_id=-300, title="A", archive_account_id=account.id)
    second = BackupChannel(main_channel_id=-101, backup_channel_id=-301, title="A2", archive_account_id=account.id)
    test_session.add_all([first, second])
    await test_session.commit()
    maker = mocker.patch.object(_sync_mixin, "async_session_maker")
    maker.return_value.__aenter__.return_value = test_session
    mocker.patch.object(worker_manager, "get_available_clients", new=AsyncMock(return_value=[MagicMock()]))
    mocker.patch.object(worker_manager, "release_clients")
    synced = []

    async def sync_archive(session, backup):
        synced.append(backup.title)
        await session.rollback()  # what _sync_topic does on a failed batch
        return 0

    mocker.patch.object(backup_service, "sync_archive", side_effect=sync_archive)

    result = await backup_service.sync_all()

    assert synced == ["A", "A2"] and not result["errors"]


# -- the login: an archive account is kept out of the streaming pool --


async def test_an_archive_login_stays_out_of_the_pool(client, admin_headers, test_session, mocker):
    from app.api.v1 import workers as workers_api

    telegram = MagicMock(
        is_connected=True,
        sign_in=AsyncMock(return_value=SimpleNamespace(is_premium=False)),
        export_session_string=AsyncMock(return_value="session"),
        get_me=AsyncMock(return_value=SimpleNamespace(is_premium=False)),
        stop=AsyncMock(),
    )
    mocker.patch.dict(workers_api._pending_auth, {"+390001": (telegram, "hash")})
    load = mocker.patch.object(worker_manager, "load_workers", new=AsyncMock())

    response = await client.post(
        "/api/v1/workers/verify-code",
        json={"phone_number": "+390001", "code": "12345", "archive": True},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    saved = await test_session.scalar(select(ArchiveAccount).where(ArchiveAccount.phone_number == "+390001"))
    assert saved is not None and saved.session_string == "session"
    load.assert_not_awaited()


# -- the backup API --


async def test_an_archive_is_made_and_filled_by_its_account(client, admin_headers, account, mocker):
    from app.api.v1 import backup as backup_api

    workers = [MagicMock()]
    mocker.patch.object(worker_manager, "primary_clients", return_value=workers)
    account_client = MagicMock()
    mocker.patch.object(backup_api, "archive_client", opened(account_client))
    join = mocker.patch.object(backup_api, "join_main", new=AsyncMock())
    made = BackupChannel(
        id=4, main_channel_id=-100, backup_channel_id=-300, title="A", is_active=True,
        is_promoted=False, synced_count=0, failure_count=0, max_failures=5,
        archive_account_id=account.id,
    )
    create = mocker.patch.object(backup_service, "create_backup_channel", new=AsyncMock(return_value=made))
    sync = mocker.patch.object(backup_service, "sync_messages", new=AsyncMock(return_value=0))
    invite = mocker.patch.object(backup_service, "invite_members", new=AsyncMock())

    response = await client.post(
        "/api/v1/backup/channels",
        json={"main_channel_id": -100, "title": "A", "archive_account_id": account.id},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["archive_account_id"] == account.id
    join.assert_awaited_once_with(workers, account_client, -100)
    assert create.await_args.args[1] is account_client  # the group is the account's
    assert create.await_args.kwargs == {"archive_account_id": account.id}
    assert sync.await_args.args[1] is account_client  # and so are the messages
    invite.assert_not_awaited()  # no worker in it


async def test_an_account_with_an_archive_group_stays(client, admin_headers, account, test_session):
    test_session.add(
        BackupChannel(main_channel_id=-100, backup_channel_id=-300, title="A", archive_account_id=account.id)
    )
    await test_session.commit()

    response = await client.delete(f"/api/v1/backup/archive-accounts/{account.id}", headers=admin_headers)

    assert response.status_code == 400
    listed = await client.get("/api/v1/backup/archive-accounts", headers=admin_headers)
    assert listed.json() == [{"id": account.id, "phone": "0000", "groups": 1}]


async def test_an_account_does_one_job_at_a_time(test_session, account, mocker):
    # The day's sync and the panel's "sync" button at once would forward the same
    # messages twice: each reads which ones are already there before forwarding
    import asyncio

    telegram = MagicMock(start=AsyncMock(), stop=AsyncMock(), export_session_string=AsyncMock(return_value="s"))
    mocker.patch.object(archive, "Client", return_value=telegram)
    inside = []

    async def job(name):
        async with archive.archive_client(test_session, account):
            inside.append(name)
            await asyncio.sleep(0)
            inside.append(name)

    await asyncio.gather(job("a"), job("b"))

    assert inside == ["a", "a", "b", "b"]
