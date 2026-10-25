"""Telegram downloads: 1 MB chunks for streaming, small windows for subtitles.

Both send upload.GetFile straight to the client's media session instead of going through
Pyrogram's get_file, which allows one download per client at a time, one request after
the other, and swallows every error (a stream just ends early). Several requests can be
in flight on one connection, and Telegram's errors arrive as they are.
"""

import asyncio
import random
import time
from contextlib import aclosing

from loguru import logger
from pyrogram import Client, raw
from pyrogram.errors import FloodPremiumWait, FloodWait, RPCError
from pyrogram.file_id import FileId

from app.models.media import MediaPart
from app.services.streaming.cache import (
    _FILE_ID_CACHE,
    PYROGRAM_CHUNK_SIZE,
    _cache_chunk,
    _get_cached_chunk,
    invalidate_file_id_cache,
)
from app.services.streaming.telegram import refresh_file_id

CHUNK_TIMEOUT = 20.0  # a request on a dead connection would otherwise hang for minutes
MAX_ATTEMPTS = 5

# Opening a media session (or following a CDN redirect) is left to Pyrogram's get_file,
# one call per client at a time so concurrent fetches don't each open a session.
_open_locks: dict[int, asyncio.Lock] = {}


async def _get_file(client: Client, fid: FileId, offset: int, limit: int) -> bytes | None:
    """One upload.GetFile on the client's media session for the file's DC.

    None when there's no such session yet or Telegram redirects to a CDN.
    """
    session = client.media_sessions.get(fid.dc_id)
    if session is None:
        return None
    r = await session.invoke(
        raw.functions.upload.GetFile(
            location=raw.types.InputDocumentFileLocation(
                id=fid.media_id,
                access_hash=fid.access_hash,
                file_reference=fid.file_reference,
                thumb_size=fid.thumbnail_size,
            ),
            offset=offset,
            limit=limit,
        ),
        sleep_threshold=client.sleep_threshold,
    )
    return r.bytes if isinstance(r, raw.types.upload.File) else None


async def read_small(client: Client, file_id: str, offset: int, length: int) -> bytes | None:
    """Read a few KB of a file with upload.GetFile instead of whole 1 MB chunks.

    Telegram wants a limit that is a power of two between 4 KB and 1 MB and a request that
    doesn't cross a 1 MB boundary: per 1 MB block, use the smallest limit-aligned window
    that covers the wanted bytes.

    Returns None when this shortcut can't be used: the file's DC has no media session yet
    (the regular chunk path creates it) or Telegram redirects to a CDN.
    """
    fid = FileId.decode(file_id)
    pieces = []
    end = offset + length
    while offset < end:
        piece_end = min(end, (offset // PYROGRAM_CHUNK_SIZE + 1) * PYROGRAM_CHUNK_SIZE)
        limit = 4096
        while offset - offset % limit + limit < piece_end:
            limit *= 2
        aligned = offset - offset % limit
        data = await _get_file(client, fid, aligned, limit)
        if data is None:
            return None
        pieces.append(data[offset - aligned : piece_end - aligned])
        offset = piece_end
    return b"".join(pieces)


async def fetch_chunk(client: Client, part: MediaPart, index: int) -> bytes:
    """Chunk `index` (1 MB) of a part, from the chunk cache or Telegram.

    Uses this client's own file_id: access hashes and file references belong to the
    account. An expired reference is refreshed at once, a FloodWait is waited out, a dead
    connection is dropped and reopened.
    """
    cached = _get_cached_chunk(part.id, index)
    if cached is not None:
        return cached

    for attempt in range(1, MAX_ATTEMPTS + 1):
        file_id = _FILE_ID_CACHE.get((part.id, id(client)), (part.telegram_file_id,))[0]
        fid = FileId.decode(file_id)
        session = client.media_sessions.get(fid.dc_id)
        try:
            data = await asyncio.wait_for(
                _get_file(client, fid, index * PYROGRAM_CHUNK_SIZE, PYROGRAM_CHUNK_SIZE),
                CHUNK_TIMEOUT,
            )
            if data is None:
                data = await asyncio.wait_for(_pyrogram_chunk(client, file_id, index), CHUNK_TIMEOUT)
            _cache_chunk(part.id, index, data)
            return data

        except (FloodWait, FloodPremiumWait) as e:
            logger.warning(f"[STREAM] {type(e).__name__} {e.value}s on part {part.id}, waiting")
            await asyncio.sleep(e.value)

        except RPCError as e:
            if "FILE_REFERENCE" not in f"{getattr(e, 'ID', '')} {e}":
                raise
            logger.warning(f"[STREAM] File reference expired for part {part.id}, refreshing")
            invalidate_file_id_cache(part.id, client_id=id(client))
            new_file_id = await refresh_file_id(part, client)
            if not new_file_id:
                raise RuntimeError("Failed to refresh expired file reference") from e
            _FILE_ID_CACHE[(part.id, id(client))] = (new_file_id, time.time())

        except (OSError, AttributeError) as e:  # TimeoutError is an OSError
            # AttributeError: Pyrogram's session desync (BadMsgNotification)
            logger.warning(
                f"[STREAM] Chunk {index} of part {part.id} failed ({type(e).__name__}: {e}), "
                f"retry {attempt}/{MAX_ATTEMPTS}"
            )
            # Drop the connection that failed (unless a concurrent fetch already did): the
            # next attempt opens a fresh one
            if session is not None and client.media_sessions.get(fid.dc_id) is session:
                client.media_sessions.pop(fid.dc_id, None)
                try:
                    await session.stop()
                except Exception:
                    pass
            # Jitter: concurrent fetches failing together shouldn't reconnect in a storm
            await asyncio.sleep(random.uniform(0.5, 2.0) if attempt == 1 else min(attempt * 2, 8))

    raise RuntimeError(f"Failed to fetch chunk {index} of part {part.id} after {MAX_ATTEMPTS} attempts")


async def _pyrogram_chunk(client: Client, file_id: str, index: int) -> bytes:
    """One chunk through Pyrogram's get_file, which opens the media session or follows a
    CDN redirect. It logs and swallows errors, so nothing coming back is raised as an
    OSError for fetch_chunk to retry (with the session now open, on the direct path)."""
    # ponytail: one call per client at a time; a CDN-served file would fetch serially
    async with _open_locks.setdefault(id(client), asyncio.Lock()):
        async with aclosing(client.stream_media(file_id, offset=index, limit=1)) as chunks:
            async for chunk in chunks:
                return chunk
    raise OSError("get_file returned no data")
