"""Backup channel — health check, failover, and fallback lookup."""

import asyncio
from datetime import datetime

from loguru import logger
from pyrogram import Client
from pyrogram.errors import (
    ChannelBanned,
    ChannelInvalid,
    ChannelPrivate,
    ChatForbidden,
    PeerIdInvalid,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.backup import ArchiveAccount, BackupChannel, BackupMessage
from app.services.backup._create_mixin import BackupCreateMixin
from app.services.backup.archive import archive_client, let_workers_in


def backup_topic_id(entry: dict | int) -> int:
    """A topic_map value: {"backup_id": id, "name": name}, or the bare id of older rows."""
    return entry["backup_id"] if isinstance(entry, dict) else entry


class BackupFailoverMixin(BackupCreateMixin):
    async def check_health(
        self,
        session: AsyncSession,
        client: Client,
        backup: BackupChannel,
    ) -> bool:
        """
        Try to reach the main channel. Increment failure_count on error.
        Returns True if the channel should be considered DEAD (failures >= max_failures).
        Returns False if healthy or not yet at the threshold.
        """
        try:
            await asyncio.wait_for(
                client.get_messages(backup.main_channel_id, message_ids=[1]),
                timeout=15.0,
            )
            if backup.failure_count > 0:
                backup.failure_count = 0
                backup.last_failure_at = None
                await session.commit()
                logger.info(f"[BACKUP] Main {backup.main_channel_id} recovered")
            return False
        except (ChannelBanned, ChannelInvalid, ChannelPrivate, ChatForbidden, PeerIdInvalid) as e:
            # Only "the channel is gone / we lost access" counts towards failover;
            # timeouts and FloodWait would otherwise auto-promote a healthy channel.
            backup.failure_count += 1
            backup.last_failure_at = datetime.utcnow()
            await session.commit()
            logger.warning(
                f"[BACKUP] Health check failed for {backup.main_channel_id}: {e} "
                f"(count={backup.failure_count}/{backup.max_failures})"
            )
            return backup.failure_count >= backup.max_failures
        except Exception as e:
            logger.warning(f"[BACKUP] Health check inconclusive for {backup.main_channel_id}: {e}")
            return False

    async def promote_to_main(
        self,
        session: AsyncSession,
        client: Client,
        backup: BackupChannel,
    ) -> BackupChannel:
        """
        Promote the backup channel to main:
        1. Redirect all MediaPart.channel_id from old main to backup channel.
        2. Mark this backup record as promoted / inactive.
        3. Create a new BackupChannel for the promoted channel.
        Returns the newly created BackupChannel.
        """
        from app.models.media import MediaPart

        old_main = backup.main_channel_id
        new_main = backup.backup_channel_id

        logger.info(f"[BACKUP] Promoting {new_main} to main (was {old_main})")

        parts_result = await session.execute(
            select(MediaPart).where(MediaPart.channel_id == old_main)
        )
        parts = parts_result.scalars().all()
        # Forwarded copies have their own message ids (and topics): moving channel_id
        # alone pointed every part at the wrong message.
        msg_rows = await session.execute(
            select(BackupMessage.main_message_id, BackupMessage.backup_message_id).where(
                BackupMessage.backup_channel_db_id == backup.id
            )
        )
        msg_map = dict(msg_rows.tuples().all())
        topic_map = backup.topic_map or {}
        unsynced = 0
        for part in parts:
            backup_msg_id = msg_map.get(part.message_id)
            if not backup_msg_id:  # never forwarded (or stored as 0): nothing to point at
                unsynced += 1
                continue
            part.channel_id = new_main
            part.message_id = backup_msg_id
            if part.topic_id is not None and str(part.topic_id) in topic_map:
                part.topic_id = backup_topic_id(topic_map[str(part.topic_id)])
        logger.info(
            f"[BACKUP] Redirected {len(parts) - unsynced} MediaPart records to new main"
            + (f", {unsynced} left on the old channel (not in the backup)" if unsynced else "")
        )

        others = await session.execute(
            select(BackupChannel).where(
                BackupChannel.main_channel_id == old_main, BackupChannel.id != backup.id
            )
        )
        for other in others.scalars().all():
            if other.archive_account_id is not None:
                await self._follow_new_main(session, other, new_main, msg_map, topic_map)
            else:
                # The workers' backup of a main group whose archive took over: lost too.
                # Left active, it would fail its health check and promote itself onto it
                other.is_active = False

        backup.is_active = False
        backup.is_promoted = True

        await session.commit()

        new_backup = await self.create_backup_channel(
            session, client, new_main, f"{backup.title} (new backup)"
        )

        logger.info(
            f"[BACKUP] Promotion complete: new main={new_main}, "
            f"new backup channel id={new_backup.id}"
        )
        return new_backup

    async def _follow_new_main(
        self,
        session: AsyncSession,
        archive: BackupChannel,
        new_main: int,
        msg_map: dict[int, int],
        topic_map: dict,
    ) -> None:
        """An archive of a main group that was replaced by its backup goes on from the new
        main group. Its copies are mapped on the old group's message ids: those that also
        reached the backup take their ids there; the others map to nothing in the new group
        and are dropped, since an old id could shadow a message of the new group."""
        rows = await session.execute(
            select(BackupMessage).where(BackupMessage.backup_channel_db_id == archive.id)
        )
        moved = []
        for row in rows.scalars().all():
            if new_id := msg_map.get(row.main_message_id):
                moved.append((new_id, row.backup_message_id, row.synced_at))
            await session.delete(row)
        # Deleted first, then inserted: updated one by one, an id taking one still in use
        # would break the (archive, message) uniqueness
        await session.flush()
        session.add_all(
            BackupMessage(
                backup_channel_db_id=archive.id,
                main_channel_id=new_main,
                main_message_id=new_id,
                backup_message_id=copy_id,
                synced_at=synced_at,
            )
            for new_id, copy_id, synced_at in moved
        )
        archive.main_channel_id = new_main
        archive.topic_map = {
            str(backup_topic_id(topic_map[key])): entry
            for key, entry in (archive.topic_map or {}).items()
            if key in topic_map
        }
        archive.synced_count = len(moved)
        logger.info(
            f"[ARCHIVE] Archive {archive.id} now follows {new_main} "
            f"({len(moved)} copies mapped there)"
        )

    async def promote_archive(self, session: AsyncSession, backup: BackupChannel) -> BackupChannel:
        """Make an archive group the main one, by hand: when the main group and the
        workers' backup are gone. The worker accounts (new ones, if the old were banned)
        join it first as admins, or none could read its files."""
        from app.core.worker_manager import worker_manager

        workers = worker_manager.primary_clients()
        if not workers:
            raise ValueError("No worker accounts: add them first")
        account = (
            await session.get(ArchiveAccount, backup.archive_account_id)
            if backup.archive_account_id
            else None
        )
        if account is None:
            raise ValueError("Not an archive, or its account was removed")
        async with archive_client(session, account) as archive:
            await let_workers_in(archive, backup.backup_channel_id, workers)
        return await self.promote_to_main(session, workers[0], backup)

    async def delete_telegram_group(self, client: Client, backup_tg_id: int) -> None:
        """Delete the Telegram supergroup via raw MTProto API."""
        from pyrogram import raw

        peer = await client.resolve_peer(backup_tg_id)
        await client.invoke(
            # resolve_peer's InputPeerChannel goes where TL wants an InputChannel, as Pyrogram's own methods do
            raw.functions.channels.DeleteChannel(channel=peer)  # pyright: ignore[reportArgumentType]
        )
        logger.info(f"[BACKUP] Deleted Telegram supergroup {backup_tg_id}")

    async def get_fallback_location(
        self,
        main_channel_id: int,
        main_message_id: int,
    ) -> tuple[int, int] | None:
        """
        Look up the backup (channel_id, message_id) for a main channel message.
        Returns None if no active backup mapping exists.
        """
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(BackupMessage, BackupChannel)
                    .join(BackupChannel, BackupMessage.backup_channel_db_id == BackupChannel.id)
                    .where(
                        BackupMessage.main_channel_id == main_channel_id,
                        BackupMessage.main_message_id == main_message_id,
                        BackupChannel.is_active == True,  # noqa: E712
                        # No worker is in an archive group: it can't serve a stream
                        BackupChannel.archive_account_id.is_(None),
                    )
                    .limit(1)
                )
                row = result.first()
                if row is None:
                    return None
                bm, bc = row
                return bc.backup_channel_id, bm.backup_message_id
        except Exception as e:
            logger.error(f"[BACKUP] Fallback lookup failed: {e}")
            return None
