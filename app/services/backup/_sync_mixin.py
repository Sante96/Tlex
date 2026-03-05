"""Backup channel — message sync logic."""

import asyncio
import random
from datetime import datetime

from loguru import logger
from pyrogram import Client, raw
from pyrogram.errors import FloodWait
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.backup import BackupChannel, BackupMessage


class BackupSyncMixin:
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
        main_channel_id = backup.main_channel_id
        backup_tg_id = backup.backup_channel_id
        topic_map: dict[str, dict] = backup.topic_map or {}

        topic_map = await self._ensure_topics_synced(
            client, main_channel_id, backup_tg_id, topic_map
        )
        backup.topic_map = topic_map

        existing_result = await session.execute(
            select(BackupMessage.main_message_id).where(
                BackupMessage.backup_channel_db_id == backup.id
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
                session, client, backup,
                main_channel_id, backup_tg_id,
                main_topic_id, backup_topic_id,
                already_synced, limit,
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
                    new_topic_id = getattr(new_topic, "id", None) or getattr(new_topic, "message_thread_id", None)
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
        backup: BackupChannel,
        main_channel_id: int,
        backup_tg_id: int,
        main_topic_id: int,
        backup_topic_id: int,
        already_synced: set[int],
        limit: int,
    ) -> int:
        """Forward new media messages from one topic to the matching backup topic."""
        pending: list[int] = []

        async for message in client.get_discussion_replies(
            main_channel_id, main_topic_id, limit=limit or 10000
        ):
            if message.id not in already_synced and (message.document or message.video):
                pending.append(message.id)

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
                        from_peer=main_peer,
                        to_peer=backup_peer,
                        id=batch_ids,
                        random_id=[random.randint(1, 2**31) for _ in batch_ids],
                        top_msg_id=backup_topic_id,
                    )
                )
                fwd_ids = [
                    u.message.id for u in result.updates
                    if hasattr(u, "message") and hasattr(u.message, "id")
                ]
                now = datetime.utcnow()
                if len(fwd_ids) == len(batch_ids):
                    pairs = zip(batch_ids, fwd_ids, strict=False)
                else:
                    pairs = zip(batch_ids, [0] * len(batch_ids), strict=False)
                for orig_id, fwd_id in pairs:
                    session.add(BackupMessage(
                        backup_channel_db_id=backup.id,
                        main_channel_id=main_channel_id,
                        main_message_id=orig_id,
                        backup_message_id=fwd_id,
                        synced_at=now,
                    ))
                    synced += 1
                await session.flush()

            except FloodWait as e:
                logger.warning(f"[BACKUP] FloodWait {e.value}s during forward")
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                logger.error(f"[BACKUP] Error forwarding batch (topic {main_topic_id}): {e}")
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(1.5)

        return synced

    async def sync_all(self) -> dict:
        """Sync all active backups and run health checks. Called by the scheduler."""
        from app.core.worker_manager import worker_manager

        result = await worker_manager.get_available_clients(limit=1)
        if not result:
            logger.warning("[BACKUP] No workers available for sync")
            return {"error": "No workers available"}

        client = result[0]
        total_synced = 0
        promoted: list[int] = []
        errors: list[str] = []

        async with async_session_maker() as session:
            backups_result = await session.execute(
                select(BackupChannel).where(BackupChannel.is_active == True)  # noqa: E712
            )
            backups = backups_result.scalars().all()

            for backup in backups:
                try:
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

        return {"synced": total_synced, "promoted": promoted, "errors": errors}
