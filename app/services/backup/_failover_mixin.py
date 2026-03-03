"""Backup channel — health check, failover, and fallback lookup."""

import asyncio
from datetime import datetime

from loguru import logger
from pyrogram import Client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.backup import BackupChannel, BackupMessage


class BackupFailoverMixin:
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
        except Exception as e:
            backup.failure_count += 1
            backup.last_failure_at = datetime.utcnow()
            await session.commit()
            logger.warning(
                f"[BACKUP] Health check failed for {backup.main_channel_id}: {e} "
                f"(count={backup.failure_count}/{backup.max_failures})"
            )
            return backup.failure_count >= backup.max_failures

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
        for part in parts:
            part.channel_id = new_main
        logger.info(f"[BACKUP] Redirected {len(parts)} MediaPart records to new main")

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

    async def delete_telegram_group(self, client: Client, backup_tg_id: int) -> None:
        """Delete the Telegram supergroup via raw MTProto API."""
        from pyrogram import raw

        peer = await client.resolve_peer(backup_tg_id)
        await client.invoke(
            raw.functions.channels.DeleteChannel(channel=peer)
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
