"""Core utility functions."""

import shutil
from datetime import UTC, datetime

from loguru import logger


def utc_now() -> datetime:
    """Return current UTC time as naive datetime (for PostgreSQL compatibility).

    PostgreSQL with asyncpg doesn't accept timezone-aware datetimes for
    TIMESTAMP WITHOUT TIME ZONE columns. This function returns a naive
    datetime with the correct UTC value.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def find_ffmpeg() -> str:
    """Find ffmpeg executable path."""
    path = shutil.which("ffmpeg")
    if path is None:
        logger.warning("ffmpeg not found in PATH, using 'ffmpeg'")
        return "ffmpeg"
    return path


def find_ffprobe() -> str:
    """Find ffprobe executable path."""
    path = shutil.which("ffprobe")
    if path is None:
        logger.warning("ffprobe not found in PATH, using 'ffprobe'")
        return "ffprobe"
    return path


def find_mkvextract() -> str:
    """Find mkvextract executable path."""
    path = shutil.which("mkvextract")
    if path is None:
        logger.warning("mkvextract not found in PATH, using 'mkvextract'")
        return "mkvextract"
    return path


def find_mkvmerge() -> str:
    """Find mkvmerge executable path."""
    path = shutil.which("mkvmerge")
    if path is None:
        logger.warning("mkvmerge not found in PATH, using 'mkvmerge'")
        return "mkvmerge"
    return path
