"""Telegram channel scanning logic."""

from loguru import logger
from pyrogram import Client

from app.config import get_settings
from app.services.scanner.models import SPLIT_PATTERN, MediaGroup, ScannedFile

settings = get_settings()


class TelegramScanner:
    """Scans Telegram channels for video files."""

    def __init__(self) -> None:
        self._video_ext = settings.video_extensions_list
        self._split_ext = settings.split_extensions_list

    def is_video_file(self, filename: str) -> bool:
        """Check if file is a video."""
        lower = filename.lower()
        for ext in self._video_ext:
            if lower.endswith(ext):
                return True
        return False

    def is_split_file(self, filename: str) -> bool:
        """Check if file is a split part."""
        lower = filename.lower()
        for ext in self._split_ext:
            if lower.endswith(ext):
                return True
        return bool(SPLIT_PATTERN.search(lower))

    def parse_filename(self, filename: str) -> tuple[str, int | None]:
        """Parse filename to get base name and split index."""
        match = SPLIT_PATTERN.search(filename)
        if match:
            split_idx = int(match.group(1)) - 1
            base_name = filename[: match.start()]
            return base_name, split_idx
        return filename, None

    def group_files(self, files: list[ScannedFile]) -> list[MediaGroup]:
        """Group files by base name (for split files)."""
        groups: dict[str, MediaGroup] = {}

        for f in files:
            if f.base_name not in groups:
                groups[f.base_name] = MediaGroup(base_name=f.base_name)
            groups[f.base_name].files.append(f)

        for group in groups.values():
            group.files.sort(key=lambda x: x.split_index if x.split_index is not None else 0)

        return list(groups.values())

    async def scan_channel(
        self, client: Client, channel_id: int, limit: int = 100, topic_id: int | None = None
    ) -> list[ScannedFile]:
        """Scan a Telegram channel for video files."""
        files: list[ScannedFile] = []

        if topic_id:
            logger.info(f"Scanning topic {topic_id} in channel {channel_id}")
            messages = client.get_discussion_replies(channel_id, topic_id, limit=limit)
        else:
            messages = client.get_chat_history(channel_id, limit=limit)

        async for message in messages:
            if not message.document and not message.video:
                continue

            doc = message.document or message.video
            if not doc.file_name:
                continue

            filename = doc.file_name

            if not self.is_video_file(filename) and not self.is_split_file(filename):
                continue

            base_name, split_idx = self.parse_filename(filename)

            scanned = ScannedFile(
                message_id=message.id,
                file_id=doc.file_id,
                file_name=filename,
                file_size=doc.file_size,
                base_name=base_name,
                channel_id=channel_id,
                topic_id=topic_id,
                split_index=split_idx,
            )
            files.append(scanned)
            logger.debug(f"Found: {filename} ({doc.file_size / 1024 / 1024:.2f} MB)")

        logger.info(f"Scanned {limit} messages, found {len(files)} video files")
        return files
