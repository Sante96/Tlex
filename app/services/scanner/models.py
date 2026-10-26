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
    def complete(self) -> bool:
        """All the file's parts are here: from .001, none missing, and the last one the
        file's remainder (smaller than the others). A scan reads the latest messages: during
        an upload, or with its limit cutting a group, it saw part of a file, and the title
        made of it never grew whole (a title is known by its first part).

        ponytail: a file of an exact multiple of the part size, or split into a lone .001,
        looks unfinished and is skipped; check the parts' total against a size if one shows up
        """
        parts = sorted(
            (f for f in self.files if f.split_index is not None), key=lambda f: f.split_index or 0
        )
        if not parts:
            return True
        if [f.split_index for f in parts] != list(range(len(parts))):
            return False
        return len(parts) > 1 and parts[-1].file_size < parts[0].file_size
