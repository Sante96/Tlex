"""Data models for scanner."""

import re
from dataclasses import dataclass, field

SPLIT_PATTERN = re.compile(r"\.(\d{3})$")


@dataclass
class ScannedFile:
    """Represents a file found in Telegram."""

    message_id: int
    file_id: str
    file_name: str
    file_size: int
    base_name: str
    channel_id: int
    topic_id: int | None = None
    split_index: int | None = None


@dataclass
class MediaGroup:
    """Group of files that form a single media item."""

    base_name: str
    files: list[ScannedFile] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(f.file_size for f in self.files)

    @property
    def is_split(self) -> bool:
        return len(self.files) > 1 or any(f.split_index is not None for f in self.files)
