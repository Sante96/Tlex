"""Scanner service for orchestrating Telegram scans."""

import asyncio

from loguru import logger
from pyrogram import Client
from pyrogram.errors import FloodWait
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.utils import flood_seconds
from app.core.worker_manager import worker_manager
from app.services.concert_frames import schedule_concert_frames
from app.services.scanner.concerts import concert_franchise_name, process_concert_group
from app.services.scanner.processor import process_group
from app.services.scanner.telegram import TelegramScanner

settings = get_settings()

# A flood wait longer than this ends the topic's scan: the next scan comes in 3 hours
MAX_FLOOD_WAIT = 300


class ScannerService:
    """High-level scanner service for orchestrating scans."""

    def __init__(self) -> None:
        self._scanner = TelegramScanner()
        self._is_scanning = False

    @property
    def is_scanning(self) -> bool:
        return self._is_scanning

    async def scan_all_channels(
        self, session: AsyncSession, limit: int = 0, topic_id: int | None = None
    ) -> dict:
        """Scan all configured channels and their topics. limit 0: every message of a
        topic. The latest 100 only left out the older files of a bulk upload (the seedbox
        puts hundreds of films in one topic between two scans); a known file costs one
        lookup."""
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
                        topic_name = await self._topic_name(client, channel_id, topic_id)
                        await self._scan_topic(
                            session,
                            client,
                            channel_id,
                            topic_id,
                            limit,
                            stats,
                            topic_name=topic_name,
                        )
                    else:
                        await self._scan_all_topics(session, client, channel_id, limit, stats)

                except Exception as e:
                    logger.error(f"Error scanning channel {channel_id}: {e}")
                    stats["errors"].append(f"Channel {channel_id}: {e}")

        finally:
            self._is_scanning = False

        # New concerts need a frame for their card (a no-op when none lack an image)
        if stats["media_created"]:
            schedule_concert_frames()
        return stats

    async def _topic_name(self, client: Client, channel_id: int, topic_id: int) -> str | None:
        """A topic scanned alone needs its name too: "Concerti · X" makes its files concerts,
        "<Title> - Stagione N" gives the series and the season."""
        try:
            topic = await client.get_forum_topic(channel_id, topic_id)
        except Exception as e:
            logger.warning(f"Topic {topic_id}: name not read, scanned without it: {e}")
            return None
        if isinstance(topic, list):
            topic = topic[0] if topic else None
        return topic.name if topic else None

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
            logger.debug(f"Getting topics for channel {channel_id}")

            # Use pyrogram's get_forum_topics method
            topics = []
            async for topic in client.get_forum_topics(channel_id):
                if topic.message_thread_id == 1:  # Skip "General" topic
                    continue
                topics.append({"id": topic.message_thread_id, "title": topic.name})
                logger.debug(f"Found topic: {topic.name} (id={topic.message_thread_id})")

            logger.debug(f"Found {len(topics)} topics to scan")

            for topic in topics:
                await self._scan_topic(
                    session,
                    client,
                    channel_id,
                    topic["id"],
                    limit,
                    stats,
                    topic_name=topic["title"],
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
            # "Concerti · <anime/game>": every file is a concert of that franchise
            franchise = None if is_movies_topic else concert_franchise_name(topic_name)
            kind = "Movies" if is_movies_topic else "Concerts" if franchise else "Series"

            logger.debug(f"Scanning topic {topic_id} ({topic_name or 'unknown'}) - Type: {kind}")

            # Telegram paces history reads: wait out its flood wait, or this topic and the
            # ones after it (the wait still running) were all skipped, every scan
            while True:
                try:
                    files = await self._scanner.scan_channel(client, channel_id, limit, topic_id)
                    break
                except FloodWait as e:
                    if flood_seconds(e) > MAX_FLOOD_WAIT:
                        raise
                    logger.info(f"Topic {topic_id}: flood wait {flood_seconds(e)} s")
                    await asyncio.sleep(flood_seconds(e) + 1)
            stats["files_found"] += len(files)
            stats["topics"] += 1

            groups = self._scanner.group_files(files)
            for group in groups:
                if not group.complete:
                    logger.info(f"Skipping {group.base_name} for now: not all its parts are here")
                    continue
                try:
                    if franchise:
                        item = await process_concert_group(session, group, client, franchise)
                    else:
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
                    # process_group commits per group: drop only this group's partial
                    # work, otherwise every later group fails with PendingRollbackError
                    await session.rollback()

        except Exception as e:
            logger.error(f"Error scanning topic {topic_id}: {e}")
            stats["errors"].append(f"Topic {topic_id}: {e}")


# Global instance
scanner_service = ScannerService()
