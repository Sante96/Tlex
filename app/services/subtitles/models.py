"""Subtitle data models."""

from dataclasses import dataclass


@dataclass
class AttachedFont:
    """Attached font from MKV container."""

    filename: str
    mimetype: str
    data: bytes
    font_names: list[str] | None = None  # Internal font names from TTF/OTF
