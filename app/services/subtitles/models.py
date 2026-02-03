"""Subtitle data models."""

from dataclasses import dataclass


@dataclass
class SubtitleTrack:
    """Extracted subtitle track info."""

    index: int
    codec: str  # ass, srt, subrip
    language: str | None
    title: str | None
    is_default: bool


@dataclass
class AttachedFont:
    """Attached font from MKV container."""

    filename: str
    mimetype: str
    data: bytes
    font_names: list[str] | None = None  # Internal font names from TTF/OTF
