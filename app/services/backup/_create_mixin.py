"""Backup channel — creation helpers."""

import asyncio

from loguru import logger
from pyrogram import Client, raw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup import BackupChannel


class BackupCreateMixin:
    async def _create_megagroup(self, client: Client, title: str, description: str) -> int:
        """
        Create a Telegram megagroup (supergroup) and enable forum topics.
        Returns the Telegram chat ID (negative).
        """
        result = await client.invoke(
            raw.functions.channels.CreateChannel(
                title=title,
                about=description,
                megagroup=True,
            )
        )
        channel = result.chats[0]
        chat_id = int(f"-100{channel.id}")
        peer = await client.resolve_peer(chat_id)

        await client.invoke(
            raw.functions.channels.ToggleForum(channel=peer, enabled=True, tabs=False)
        )
        logger.info(f"[BACKUP] Created megagroup id={chat_id} with forum enabled")
        return chat_id

    async def _mirror_topics(
        self, client: Client, main_channel_id: int, backup_tg_id: int
    ) -> dict[str, dict]:
        """
        Read all topics from the main channel and create matching ones in the backup.
        Returns topic_map: {str(main_topic_id): {"backup_id": int, "name": str}}.
        """
        topic_map: dict[str, dict] = {}

        async for topic in client.get_forum_topics(main_channel_id):
            if topic.message_thread_id == 1:
                continue
            try:
                new_topic = await client.create_forum_topic(backup_tg_id, topic.name)
                new_topic_id = getattr(new_topic, "id", None) or getattr(new_topic, "message_thread_id", None)
                if not new_topic_id:
                    logger.warning(f"[BACKUP] Could not extract topic id for '{topic.name}', skipping")
                    continue
                topic_map[str(topic.message_thread_id)] = {
                    "backup_id": new_topic_id,
                    "name": topic.name,
                }
                logger.info(
                    f"[BACKUP] Mirrored topic '{topic.name}' "
                    f"{topic.message_thread_id} → {new_topic_id}"
                )
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"[BACKUP] Failed to create topic '{topic.name}': {e}")

        return topic_map

    async def create_backup_channel(
        self,
        session: AsyncSession,
        client: Client,
        main_channel_id: int,
        title: str,
    ) -> BackupChannel:
        """
        Create a megagroup with forum topics mirroring the main channel,
        then mirror all existing topics. Save to DB.
        """
        existing = await session.execute(
            select(BackupChannel).where(BackupChannel.main_channel_id == main_channel_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"A backup already exists for channel {main_channel_id}")

        logger.info(f"[BACKUP] Creating megagroup for {main_channel_id} titled '{title}'")

        backup_tg_id = await self._create_megagroup(
            client, title, f"Backup of channel {main_channel_id}"
        )
        topic_map = await self._mirror_topics(client, main_channel_id, backup_tg_id)

        backup = BackupChannel(
            main_channel_id=main_channel_id,
            backup_channel_id=backup_tg_id,
            title=title,
            topic_map=topic_map,
        )
        session.add(backup)
        await session.commit()
        await session.refresh(backup)

        logger.info(f"[BACKUP] BackupChannel saved: id={backup.id}, topics={len(topic_map)}")
        return backup
