"""Scanner service for orchestrating Telegram scans."""

from loguru import logger
from pyrogram import Client
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.services.scanner.processor import process_group
from app.services.scanner.telegram import TelegramScanner

settings = get_settings()


class ScannerService:
    """High-level scanner service for orchestrating scans."""

    def __init__(self) -> None:
        self._scanner = TelegramScanner()
        self._is_scanning = False

    @property
    def is_scanning(self) -> bool:
        return self._is_scanning

    async def scan_all_channels(
        self, session: AsyncSession, limit: int = 100, topic_id: int | None = None
    ) -> dict:
        """Scan all configured channels and their topics."""
        if self._is_scanning:
            return {"error": "Scan already in progress"}

        self._is_scanning = True
        stats = {"channels": 0, "topics": 0, "files_found": 0, "media_created": 0, "errors": []}

        try:
            channel_ids = settings.channel_ids_list
            if not channel_ids:
                return {"error": "No channels configured"}

            result = await worker_manager.get_best_worker(session)
            if not result:
                return {"error": "No workers available"}

            worker, client = result

            for channel_id in channel_ids:
                try:
                    stats["channels"] += 1

                    if topic_id:
                        await self._scan_topic(
                            session, client, channel_id, topic_id, limit, stats, topic_name=None
                        )
                    else:
                        await self._scan_all_topics(session, client, channel_id, limit, stats)

                except Exception as e:
                    logger.error(f"Error scanning channel {channel_id}: {e}")
                    stats["errors"].append(f"Channel {channel_id}: {e}")

        finally:
            self._is_scanning = False

        return stats

    async def _scan_all_topics(
        self,
        session: AsyncSession,
        client: Client,
        channel_id: int,
        limit: int,
        stats: dict,
    ) -> None:
        """Scan all topics in a forum channel."""
        try:
            from pyrogram.raw import functions

            logger.debug(f"Getting topics for channel {channel_id}")

            async for dialog in client.get_dialogs():
                if dialog.chat.id == channel_id:
                    break

            peer = await client.resolve_peer(channel_id)
            result = await client.invoke(
                functions.channels.GetForumTopics(
                    channel=peer,
                    offset_date=0,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )

            topics = []
            for topic in result.topics:
                if hasattr(topic, "title") and hasattr(topic, "id"):
                    if topic.id == 1:
                        continue
                    topics.append({"id": topic.id, "title": topic.title})
                    logger.debug(f"Found topic: {topic.title} (id={topic.id})")

            logger.debug(f"Found {len(topics)} topics to scan")

            for topic in topics:
                await self._scan_topic(
                    session, client, channel_id, topic["id"], limit, stats, topic_name=topic["title"]
                )

        except Exception as e:
            logger.error(f"Error getting topics: {e}")
            stats["errors"].append(f"Get topics: {e}")

    async def _scan_topic(
        self,
        session: AsyncSession,
        client: Client,
        channel_id: int,
        topic_id: int,
        limit: int,
        stats: dict,
        topic_name: str | None = None,
    ) -> None:
        """Scan a single topic and process files."""
        try:
            is_movies_topic = topic_id == settings.scanner_movies_topic_id

            logger.debug(
                f"Scanning topic {topic_id} ({topic_name or 'unknown'})"
                f" - Type: {'Movies' if is_movies_topic else 'Series'}"
            )

            files = await self._scanner.scan_channel(client, channel_id, limit, topic_id)
            stats["files_found"] += len(files)
            stats["topics"] += 1

            groups = self._scanner.group_files(files)
            for group in groups:
                try:
                    item = await process_group(
                        session,
                        group,
                        client,
                        force_movie=is_movies_topic,
                        series_name=topic_name if not is_movies_topic else None,
                    )
                    if item:
                        stats["media_created"] += 1
                except Exception as e:
                    logger.error(f"Error processing {group.base_name}: {e}")
                    stats["errors"].append(str(e))

        except Exception as e:
            logger.error(f"Error scanning topic {topic_id}: {e}")
            stats["errors"].append(f"Topic {topic_id}: {e}")


# Global instance
scanner_service = ScannerService()
