"""Backup channel — member invitation and admin promotion."""

import asyncio

from loguru import logger
from pyrogram import Client
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait, PeerIdInvalid, RPCError, UserPrivacyRestricted
from pyrogram.types import ChatPrivileges
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import flood_seconds
from app.core.worker_manager import worker_manager
from app.models.backup import BackupChannel
from app.models.media import MediaPart
from app.services.backup.archive import WORKER_RIGHTS, _join, chat_ids


class BackupMembersMixin:
    async def join_library_groups(
        self, session: AsyncSession, joining: list[Client] | None = None
    ) -> None:
        """Each worker account in `joining` (all if None) joins the groups the files are in,
        and their backups, as an admin like the others. Added from the admin panel, an
        account was in none: every stream that drew one of its clients failed
        (CHANNEL_INVALID). The link and the rights come from an account already in."""
        accounts = worker_manager.primary_clients()
        groups = set(await session.scalars(select(distinct(MediaPart.channel_id))))
        # Not the archive groups: no worker is in those, so a ban can't take them down
        groups |= set(
            await session.scalars(
                select(BackupChannel.backup_channel_id).where(
                    BackupChannel.is_active, BackupChannel.archive_account_id.is_(None)
                )
            )
        )
        chats = {client: await chat_ids(client) for client in accounts}
        for client in joining or accounts:
            me = client.me or await client.get_me()  # set by start(), typed optional
            for group in sorted(groups - chats[client]):
                inside = [a for a in accounts if group in chats[a]]
                for member in inside:
                    try:
                        await _join(member, group, client)
                        # Promoting takes the user's access hash, learnt by reading them
                        # Pyrogram annotates its async generators as coroutines
                        async for _ in member.get_chat_members(group):  # pyright: ignore[reportGeneralTypeIssues]
                            pass
                        await member.promote_chat_member(group, me.id, privileges=WORKER_RIGHTS)
                    except RPCError as e:
                        logger.debug(f"[WORKERS] {group}: no invite from this account ({e})")
                        continue
                    logger.info(f"[WORKERS] {me.phone_number} joined {group}")
                    break
                else:
                    logger.warning(
                        f"[WORKERS] {me.phone_number} is not in {group}, and no account "
                        "already in it could let it in: add it by hand"
                    )
        logger.info(
            f"[WORKERS] {len(joining or accounts)} account(s) checked in {len(groups)} group(s)"
        )

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
        # Pyrogram annotates its async generators as coroutines
        async for member in client.get_chat_members(main_channel_id):  # pyright: ignore[reportGeneralTypeIssues]
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
                    logger.warning(f"FloodWait {flood_seconds(e)}s while inviting members")
                    await asyncio.sleep(flood_seconds(e) + 1)
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

        # Pyrogram annotates its async generators as coroutines
        async for member in client.get_chat_members(  # pyright: ignore[reportGeneralTypeIssues]
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
                await asyncio.sleep(flood_seconds(e) + 1)
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
