"""Own images: a concert's frame, an uploaded file, a picture downloaded from a link.

Kept under IMAGES_DIR (a volume of its own: uploads can't be made again, unlike the
cache) and written into poster_path/backdrop_path as "local:<name>", next to TMDB's
"/abc.jpg" paths. Names are random, so the public GET reveals nothing by guessing.
"""

import asyncio
import ipaddress
import re
import socket
from pathlib import Path
from uuid import uuid4

import httpx

IMAGES_DIR = Path("images")
MAX_IMAGE_BYTES = 10 * 1024 * 1024
LOCAL_PREFIX = "local:"
MAX_REDIRECTS = 3
MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
_NAME = re.compile(r"[0-9a-f]{32}\.(jpg|png|webp)")


class ImageError(ValueError):
    """Why an image was refused, for the person who chose it."""


def image_type(data: bytes) -> str | None:
    """The image format from the file's first bytes (not from what the sender claims)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(data: bytes) -> str:
    """Store an image under a random name; returns its "local:<name>" path."""
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError("The image is larger than 10 MB")
    ext = image_type(data)
    if ext is None:
        raise ImageError("Not a JPEG, PNG or WebP image")
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4().hex}.{ext}"
    (IMAGES_DIR / name).write_bytes(data)
    return LOCAL_PREFIX + name


def image_file(name: str) -> Path | None:
    """The stored image of that name; None for any other name (no paths, no guessing)."""
    if not _NAME.fullmatch(name):
        return None
    path = IMAGES_DIR / name
    return path if path.is_file() else None


async def _check_public(url: str) -> httpx.URL:
    """The link, if it's http(s) to public addresses only: the backend fetches it, and
    must not be pointed at itself, the Docker network or the LAN."""
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL as e:
        raise ImageError("Not a valid link") from e
    if parsed.scheme not in ("http", "https") or not parsed.host:
        raise ImageError("Only http(s) links to an image")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, parsed.host, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as e:
        raise ImageError("Unknown host") from e
    for *_, sockaddr in infos:
        try:
            public = ipaddress.ip_address(sockaddr[0]).is_global
        except ValueError:
            public = False
        if not public:
            raise ImageError("Links to local or private addresses are not allowed")
    # ponytail: checked, then resolved again by httpx (DNS rebinding could slip
    # through); pin the checked address if links ever come from untrusted users
    return parsed


async def fetch_image(url: str, transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    """Download an image from a pasted link, within the size limit."""
    target = await _check_public(url)
    async with httpx.AsyncClient(follow_redirects=False, timeout=15, transport=transport) as client:
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", target) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location", "")
                    target = await _check_public(str(resp.url.join(location)))
                    continue
                if resp.status_code != 200:
                    raise ImageError(f"The link answered {resp.status_code}")
                data = bytearray()
                async for chunk in resp.aiter_bytes():
                    data += chunk
                    if len(data) > MAX_IMAGE_BYTES:
                        raise ImageError("The image is larger than 10 MB")
                return bytes(data)
    raise ImageError("Too many redirects")
