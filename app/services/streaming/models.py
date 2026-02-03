"""Streaming data models."""

from dataclasses import dataclass

from app.models.media import MediaPart


@dataclass
class StreamPosition:
    """Current position in the virtual stream."""

    part: MediaPart
    local_offset: int  # Offset within the current part
