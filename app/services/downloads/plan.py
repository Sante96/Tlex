"""Where a downloaded torrent's files go in Telegram, and what to read from a torrent."""

from typing import Any
from urllib.parse import parse_qs, urlparse

from guessit import guessit

from app.config import get_settings
from app.models.download import DownloadKind
from app.services.scanner.processor import special_number
from app.services.scanner.telegram import TelegramScanner

_SKIPPED_DIRS = {"extra", "extras", "bonus", "ncop", "nced", "nc"}


def destination_topic(kind: DownloadKind, name: str | None, season: int | None) -> str | int:
    """The films topic id, or the name of a topic the scanner reads."""
    if kind == DownloadKind.film:
        topic_id = get_settings().scanner_movies_topic_id
        if topic_id is None:
            raise ValueError("SCANNER_MOVIES_TOPIC_ID is not set")
        return topic_id
    if not name:
        raise ValueError("a name is required for this kind of download")
    if kind == DownloadKind.concert:
        return f"Concerti · {name}"
    return f"{name} - Stagione {season if season is not None else 1}"


def file_topic(kind: DownloadKind, name: str | None, season: int | None, path: str) -> str | int:
    """A pack holds several seasons and specials: each file goes to its own topic."""
    if kind not in (DownloadKind.series, DownloadKind.anime):
        return destination_topic(kind, name, season)
    if special_number(path) is not None:
        return destination_topic(kind, name, 0)
    file_season = guessit(path.replace("\\", "/").rsplit("/", 1)[-1]).get("season")
    if isinstance(file_season, list):
        file_season = file_season[0]
    return destination_topic(kind, name, file_season or season or 1)


def uploadable(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    if not TelegramScanner().is_video_file(parts[-1]):
        return False
    return not any("sample" in p.lower() or p.lower() in _SKIPPED_DIRS for p in parts)


def _bdecode(data: bytes, i: int = 0) -> tuple[Any, int]:
    """Minimal bencode: ints, byte strings, lists, dicts. Raises on malformed input."""
    c = data[i : i + 1]
    if c == b"i":
        end = data.index(b"e", i)
        return int(data[i + 1 : end]), end + 1
    if c in (b"l", b"d"):
        i += 1
        items = []
        while data[i : i + 1] != b"e":
            item, i = _bdecode(data, i)
            items.append(item)
        if c == b"l":
            return items, i + 1
        return dict(zip(items[::2], items[1::2], strict=True)), i + 1
    colon = data.index(b":", i)
    start = colon + 1
    end = start + int(data[i:colon])
    if end > len(data):
        raise ValueError("truncated")
    return data[start:end], end


def torrent_name(magnet: str | None, torrent: bytes | None) -> str | None:
    if magnet:
        dn = parse_qs(urlparse(magnet).query).get("dn")
        return dn[0] if dn else None
    if torrent:
        try:
            name = _bdecode(torrent)[0][b"info"][b"name"]
            return name.decode("utf-8", errors="replace")
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            return None
    return None


def info_hash(magnet: str) -> str | None:
    for xt in parse_qs(urlparse(magnet).query).get("xt", []):
        if xt.lower().startswith("urn:btih:"):
            return xt[9:].lower()
    return None


def guess(torrent_name: str) -> dict:
    info = guessit(torrent_name)
    season = info.get("season")
    if isinstance(season, list):
        season = season[0]
    return {"name": info.get("title"), "season": season}
