"""Backup channel — member invitation and admin promotion."""

import asyncio

from loguru import logger
from pyrogram import Client
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait, PeerIdInvalid, UserPrivacyRestricted
from pyrogram.types import ChatPrivileges


class BackupMembersMixin:
    async def invite_members(
        self,
        client: Client,
        main_channel_id: int,
        backup_channel_id: int,
    ) -> int:
        """
        Copy all participants from the main channel to the backup.
        Returns number of members successfully invited.
        """
        invited = 0
        failed = 0

        logger.info(f"Inviting members from {main_channel_id} to {backup_channel_id}")

        user_ids: list[int] = []
        async for member in client.get_chat_members(main_channel_id):
            if member.user and not member.user.is_bot and not member.user.is_deleted:
                user_ids.append(member.user.id)

        logger.info(f"Found {len(user_ids)} members to invite")

        BATCH = 20
        for i in range(0, len(user_ids), BATCH):
            batch = user_ids[i : i + BATCH]
            for uid in batch:
                try:
                    await client.add_chat_members(backup_channel_id, uid)
                    invited += 1
                except FloodWait as e:
                    logger.warning(f"FloodWait {e.value}s while inviting members")
                    await asyncio.sleep(e.value + 1)
                    try:
                        await client.add_chat_members(backup_channel_id, uid)
                        invited += 1
                    except Exception:
                        failed += 1
                except (UserPrivacyRestricted, PeerIdInvalid):
                    failed += 1
                except Exception as e:
                    logger.warning(f"Failed to invite user {uid}: {e}")
                    failed += 1
            await asyncio.sleep(1)

        logger.info(f"Invited {invited} members, {failed} failed")
        return invited

    async def promote_admins(
        self,
        client: Client,
        main_channel_id: int,
        backup_channel_id: int,
    ) -> int:
        """
        Fetch all admins from the main channel and promote them to admin
        in the backup group with full privileges.
        Returns number of successfully promoted admins.
        """
        promoted = 0
        full_privileges = ChatPrivileges(
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=True,
            can_change_info=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_manage_topics=True,
        )

        logger.info(f"[BACKUP] Promoting admins from {main_channel_id} to {backup_channel_id}")

        async for member in client.get_chat_members(
            main_channel_id, filter=ChatMembersFilter.ADMINISTRATORS
        ):
            if not member.user or member.user.is_bot or member.user.is_deleted:
                continue
            try:
                await client.add_chat_members(backup_channel_id, member.user.id)
            except Exception:
                pass
            try:
                await client.promote_chat_member(
                    backup_channel_id, member.user.id, privileges=full_privileges
                )
                promoted += 1
                logger.info(f"[BACKUP] Promoted admin {member.user.id} (@{member.user.username})")
                await asyncio.sleep(0.5)
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                try:
                    await client.promote_chat_member(
                        backup_channel_id, member.user.id, privileges=full_privileges
                    )
                    promoted += 1
                except Exception as err:
                    logger.warning(f"[BACKUP] Failed to promote {member.user.id}: {err}")
            except Exception as e:
                logger.warning(f"[BACKUP] Failed to promote {member.user.id}: {e}")

        logger.info(f"[BACKUP] Promoted {promoted} admins")
        return promoted
