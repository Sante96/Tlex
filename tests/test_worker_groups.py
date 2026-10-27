"""A worker account added from the admin panel joins the groups the files are in, and
their backups: in none, every stream that drew one of its clients failed (CHANNEL_INVALID)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pyrogram.errors import ChatAdminRequired

from app.core.worker_manager import worker_manager
from app.models.backup import ArchiveAccount, BackupChannel
from app.models.media import MediaItem, MediaPart, MediaType
from app.services.backup import backup_service


def account(user_id: int, *chat_ids: int) -> MagicMock:
    """A worker account's primary client, a member of these chats."""

    async def get_dialogs():
        for chat_id in chat_ids:
            yield SimpleNamespace(chat=SimpleNamespace(id=chat_id))

    async def get_chat_members(chat_id):
        yield SimpleNamespace(user=SimpleNamespace(id=user_id))

    return MagicMock(
        me=SimpleNamespace(id=user_id, phone_number=f"+39{user_id}"),
        get_dialogs=get_dialogs,
        get_chat_members=get_chat_members,
        join_chat=AsyncMock(),
        promote_chat_member=AsyncMock(),
        create_chat_invite_link=AsyncMock(
            side_effect=lambda chat_id, member_limit: SimpleNamespace(
                invite_link=f"link-{user_id}-{chat_id}"
            )
        ),
    )


async def test_a_new_worker_joins_the_files_group_and_its_backup(test_session, mocker):
    item = MediaItem(title="Laid-Back Camp 1", media_type=MediaType.EPISODE)
    test_session.add(item)
    await test_session.flush()
    archive_owner = ArchiveAccount(phone_number="+390000", session_string="s")
    test_session.add(archive_owner)
    await test_session.flush()
    test_session.add_all([
        MediaPart(media_item_id=item.id, telegram_file_id="f", part_index=0, start_byte=0,
                  end_byte=9, file_size=10, channel_id=-100, message_id=1),
        BackupChannel(main_channel_id=-100, backup_channel_id=-200, title="B"),
        # An archive group stays without workers: that's its point
        BackupChannel(main_channel_id=-100, backup_channel_id=-300, title="A",
                      archive_account_id=archive_owner.id),
    ])
    await test_session.commit()
    # 10 is in the main group but can't invite; 12 is an admin of both; 14 is new
    not_admin = account(10, -100)
    not_admin.create_chat_invite_link = AsyncMock(side_effect=ChatAdminRequired())
    admin = account(12, -100, -200, -300)
    new = account(14)
    mocker.patch.object(worker_manager, "primary_clients", return_value=[not_admin, admin, new])

    await backup_service.join_library_groups(test_session, [new])

    joined = sorted(c.args[0] for c in new.join_chat.await_args_list)
    assert joined == ["link-12--100", "link-12--200"]
    # Admins, as the others: topics and invite links in the backup sync
    promoted = sorted(c.args[:2] for c in admin.promote_chat_member.await_args_list)
    assert promoted == [(-200, 14), (-100, 14)]


async def test_an_account_already_in_is_left_alone(test_session, mocker):
    item = MediaItem(title="Invincible 1", media_type=MediaType.EPISODE)
    test_session.add(item)
    await test_session.flush()
    test_session.add(
        MediaPart(media_item_id=item.id, telegram_file_id="f", part_index=0, start_byte=0,
                  end_byte=9, file_size=10, channel_id=-100, message_id=1)
    )
    await test_session.commit()
    admin = account(12, -100)
    other = account(13, -100)
    mocker.patch.object(worker_manager, "primary_clients", return_value=[admin, other])

    await backup_service.join_library_groups(test_session)

    admin.create_chat_invite_link.assert_not_awaited()
    other.create_chat_invite_link.assert_not_awaited()
