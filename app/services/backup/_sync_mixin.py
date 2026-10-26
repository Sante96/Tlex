"""Backup channel — message sync logic."""

import asyncio
import random
from datetime import datetime, timedelta

from loguru import logger
from pyrogram import Client, raw
from pyrogram.errors import FloodWait
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import flood_seconds
from app.database import async_session_maker
from app.models.backup import ArchiveAccount, BackupChannel, BackupMessage
from app.services.backup._failover_mixin import BackupFailoverMixin
from app.services.backup.archive import archive_client, join_main

# A day, give or take the scheduler's tick (6 h by default): the archive account goes
# online once a day
ARCHIVE_SYNC_EVERY = timedelta(hours=20)


class BackupSyncMixin(BackupFailoverMixin):
    async def sync_archive(self, session: AsyncSession, backup: BackupChannel) -> int:
        """Fill an archive group from its own account. A worker account only lets it into
        the main group when it isn't a member."""
        from app.core.worker_manager import worker_manager

        account = await session.get(ArchiveAccount, backup.archive_account_id)
        if account is None:
            return 0
        async with archive_client(session, account) as archive:
            await join_main(worker_manager.primary_clients(), archive, backup.main_channel_id)
            return await self.sync_messages(session, archive, backup)

    async def sync_messages(
        self,
        session: AsyncSession,
        client: Client,
        backup: BackupChannel,
        limit: int = 0,
    ) -> int:
        """
        Forward all new media messages from each topic in the main channel
        to the corresponding topic in the backup. Returns total synced count.
        """
        # Read once: a failed batch's rollback expires `backup`, and reloading an attribute
        # in async code raises MissingGreenlet
        backup_id = backup.id
        main_channel_id = backup.main_channel_id
        backup_tg_id = backup.backup_channel_id
        topic_map: dict[str, dict] = backup.topic_map or {}

        topic_map = await self._ensure_topics_synced(
            client, main_channel_id, backup_tg_id, topic_map
        )
        backup.topic_map = topic_map
        await session.commit()  # topics just created on Telegram must not be created again

        existing_result = await session.execute(
            select(BackupMessage.main_message_id).where(
                BackupMessage.backup_channel_db_id == backup_id
            )
        )
        already_synced: set[int] = set(existing_result.scalars().all())

        logger.info(
            f"[BACKUP] Syncing {main_channel_id} → {backup_tg_id} "
            f"({len(topic_map)} topics, {len(already_synced)} already synced)"
        )

        total_synced = 0

        for main_topic_id_str, entry in topic_map.items():
            main_topic_id = int(main_topic_id_str)
            backup_topic_id = entry["backup_id"]
            synced = await self._sync_topic(
                session,
                client,
                backup_id,
                main_channel_id,
                backup_tg_id,
                main_topic_id,
                backup_topic_id,
                already_synced,
                limit,
            )
            total_synced += synced

        backup.synced_count = len(already_synced) + total_synced
        backup.last_sync_at = datetime.utcnow()
        await session.commit()

        logger.info(f"[BACKUP] Total synced: {total_synced} messages")
        return total_synced

    async def _ensure_topics_synced(
        self,
        client: Client,
        main_channel_id: int,
        backup_tg_id: int,
        topic_map: dict[str, dict],
    ) -> dict[str, dict]:
        """Create backup topics for any new topics found in the main channel."""
        updated = dict(topic_map)

        async for topic in client.get_forum_topics(main_channel_id):
            if topic.message_thread_id == 1:
                continue
            key = str(topic.message_thread_id)
            if key not in updated:
                try:
                    new_topic = await client.create_forum_topic(backup_tg_id, topic.name)
                    new_topic_id = getattr(new_topic, "id", None) or getattr(
                        new_topic, "message_thread_id", None
                    )
                    if new_topic_id:
                        updated[key] = {"backup_id": new_topic_id, "name": topic.name}
                        logger.info(f"[BACKUP] New topic '{topic.name}' mirrored → {new_topic_id}")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"[BACKUP] Failed to mirror new topic '{topic.name}': {e}")

        return updated

    async def _sync_topic(
        self,
        session: AsyncSession,
        client: Client,
        backup_id: int,
        main_channel_id: int,
        backup_tg_id: int,
        main_topic_id: int,
        backup_topic_id: int,
        already_synced: set[int],
        limit: int,
    ) -> int:
        """Forward new media messages from one topic to the matching backup topic."""
        pending: list[int] = []
        while True:
            try:
                # Pyrogram annotates its async generators as coroutines
                async for message in client.get_discussion_replies(  # pyright: ignore[reportGeneralTypeIssues]
                    main_channel_id, main_topic_id, limit=limit or 10000
                ):
                    if message.id not in already_synced and (message.document or message.video):
                        pending.append(message.id)
                break
            except FloodWait as e:
                # Reading every topic in a row, Telegram asks to slow down (16 s seen): the
                # error ended the whole sync, every hour, after the new topics were made,
                # and they stayed empty. Waited out, the topic is read again
                logger.warning(
                    f"[BACKUP] FloodWait {flood_seconds(e)}s reading topic {main_topic_id}"
                )
                await asyncio.sleep(flood_seconds(e) + 1)
                pending = []

        if not pending:
            return 0

        logger.info(
            f"[BACKUP] Topic {main_topic_id} → {backup_topic_id}: "
            f"forwarding {len(pending)} messages"
        )

        synced = 0
        BATCH = 100
        for i in range(0, len(pending), BATCH):
            batch_ids = pending[i : i + BATCH]
            try:
                backup_peer = await client.resolve_peer(backup_tg_id)
                main_peer = await client.resolve_peer(main_channel_id)
                result = await client.invoke(
                    raw.functions.messages.ForwardMessages(
                        from_peer=main_peer,  # pyright: ignore[reportArgumentType]
                        to_peer=backup_peer,  # pyright: ignore[reportArgumentType]
                        id=batch_ids,
                        random_id=[random.randint(1, 2**31) for _ in batch_ids],
                        top_msg_id=backup_topic_id,
                    )
                )
                # The forwarded copies come back as UpdateNew(Channel)Message entries
                fwd_ids = [
                    m.id
                    for u in getattr(result, "updates", [])
                    if (m := getattr(u, "message", None)) is not None and hasattr(m, "id")
                ]
                now = datetime.utcnow()
                if len(fwd_ids) == len(batch_ids):
                    pairs = zip(batch_ids, fwd_ids, strict=False)
                else:
                    pairs = zip(batch_ids, [0] * len(batch_ids), strict=False)
                for orig_id, fwd_id in pairs:
                    session.add(
                        BackupMessage(
                            backup_channel_db_id=backup_id,
                            main_channel_id=main_channel_id,
                            main_message_id=orig_id,
                            backup_message_id=fwd_id,
                            synced_at=now,
                        )
                    )
                    synced += 1
                # Commit each batch: these messages are on Telegram now, and a later
                # batch's rollback must not drop them (the next run would forward them again)
                await session.commit()

            except FloodWait as e:
                logger.warning(f"[BACKUP] FloodWait {flood_seconds(e)}s during forward")
                await asyncio.sleep(flood_seconds(e) + 1)
            except Exception as e:
                logger.error(f"[BACKUP] Error forwarding batch (topic {main_topic_id}): {e}")
                await session.rollback()
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(1.5)

        return synced

    async def sync_all(self) -> dict:
        """Sync all active backups and run health checks. Called by the scheduler."""
        from app.core.worker_manager import worker_manager

        total_synced = 0
        promoted: list[int] = []
        errors: list[str] = []

        async with async_session_maker() as session:
            backups_result = await session.execute(
                select(BackupChannel).where(BackupChannel.is_active == True)  # noqa: E712
            )
            backups = backups_result.scalars().all()
            if not backups:
                return {"synced": 0, "promoted": [], "errors": []}

            result = await worker_manager.get_available_clients(limit=1)
            if not result:
                logger.warning("[BACKUP] No workers available for sync")
                return {"error": "No workers available"}
            client = result[0]

            try:
                for backup in backups:
                    try:
                        # A failed batch of the previous one rolled the session back,
                        # expiring this row: read in async code, it would raise
                        await session.refresh(backup)
                        if backup.archive_account_id is not None:
                            # Never health-checked nor promoted on its own: by hand only
                            last = backup.last_sync_at
                            if last is None or datetime.utcnow() - last >= ARCHIVE_SYNC_EVERY:
                                total_synced += await self.sync_archive(session, backup)
                            continue

                        is_dead = await self.check_health(session, client, backup)
                        if is_dead:
                            logger.warning(
                                f"[BACKUP] Main channel {backup.main_channel_id} declared dead "
                                f"(failures={backup.failure_count}). Auto-promoting backup id={backup.id}"
                            )
                            new_backup = await self.promote_to_main(session, client, backup)
                            promoted.append(new_backup.id)
                            continue

                        count = await self.sync_messages(session, client, backup)
                        total_synced += count
                    except Exception as e:
                        msg = f"Backup id={backup.id}: {e}"
                        logger.error(f"[BACKUP] Sync error — {msg}")
                        errors.append(msg)
            finally:
                # get_available_clients marks the client in use; without this every
                # run leaked one and streaming starved after a few runs.
                worker_manager.release_clients([client])

        return {"synced": total_synced, "promoted": promoted, "errors": errors}
