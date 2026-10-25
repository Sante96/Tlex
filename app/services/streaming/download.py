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
from pyrogram.errors import BadMsgNotification, FloodPremiumWait, FloodWait, RPCError
from pyrogram.file_id import FileId, FileIdCached

from app.core.utils import flood_seconds
from app.core.worker_manager import worker_manager
from app.models.media import MediaPart
from app.services.streaming.cache import (
    FILE_ID_CACHE,
    PYROGRAM_CHUNK_SIZE,
    cache_chunk,
    get_cached_chunk,
    invalidate_file_id_cache,
)
from app.services.streaming.telegram import refresh_file_id

CHUNK_TIMEOUT = 20.0  # a request on a dead connection would otherwise hang for minutes
RECONNECT_TIMEOUT = 10.0  # Telegram closes busy media connections often; Pyrogram reconnects
MAX_ATTEMPTS = 5


class Throttled(Exception):
    """Telegram is slowing this client's account down (FLOOD_PREMIUM_WAIT, the free-tier
    download limit): the caller should use a client of another account meanwhile."""

    def __init__(self, seconds: int):
        super().__init__(f"account throttled for {seconds}s")
        self.seconds = seconds


class SessionDown(Exception):
    """The client's media connection is being re-established (Telegram drops busy media
    connections, with -429 transport floods in bursts): the caller should give the chunk
    to another client instead of waiting for this one."""


def connected(client: Client) -> bool:
    """False while one of the client's media sessions is reconnecting."""
    return all(s.is_connected.is_set() for s in client.media_sessions.values())


# Opening a media session (or following a CDN redirect) is left to Pyrogram's get_file,
# one call per client at a time so concurrent fetches don't each open a session.
_open_locks: dict[int, asyncio.Lock] = {}


def _decode(file_id: str) -> FileIdCached:
    # This Pyrogram fork's FileId.decode builds a FileIdCached, typed as possibly None
    fid = FileId.decode(file_id)
    if fid is None:
        raise ValueError(f"Undecodable file_id {file_id[:16]}...")
    return fid


async def _get_file(client: Client, fid: FileIdCached, offset: int, limit: int) -> bytes | None:
    """One upload.GetFile on the client's media session for the file's DC.

    None when there's no such session yet or Telegram redirects to a CDN.
    """
    session = client.media_sessions.get(fid.dc_id)
    if session is None:
        return None
    # send, not invoke: invoke silently sleeps out FloodWaits up to the client's
    # sleep_threshold, so a throttled account would stall the stream unseen. Like invoke,
    # wait for a session Telegram just disconnected to come back first.
    if not session.is_connected.is_set():
        await asyncio.wait_for(session.is_connected.wait(), RECONNECT_TIMEOUT)
    r = await session.send(
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
        timeout=CHUNK_TIMEOUT,
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
    fid = _decode(file_id)
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
    account. An expired reference is refreshed at once, a FloodWait is waited out. Raises
    Throttled when the account is being slowed down, SessionDown while Pyrogram
    reconnects a connection Telegram closed.
    """
    cached = get_cached_chunk(part.id, index)
    if cached is not None:
        return cached

    for attempt in range(1, MAX_ATTEMPTS + 1):
        file_id = FILE_ID_CACHE.get((part.id, id(client)), (part.telegram_file_id,))[0]
        fid = _decode(file_id)
        session = client.media_sessions.get(fid.dc_id)
        try:
            data = await asyncio.wait_for(
                _get_file(client, fid, index * PYROGRAM_CHUNK_SIZE, PYROGRAM_CHUNK_SIZE),
                CHUNK_TIMEOUT,
            )
            if data is None:
                data = await asyncio.wait_for(
                    _pyrogram_chunk(client, file_id, index), CHUNK_TIMEOUT
                )
            cache_chunk(part.id, index, data)
            return data

        except FloodPremiumWait as e:
            worker_manager.mark_throttled(client, flood_seconds(e))
            raise Throttled(flood_seconds(e)) from e

        except FloodWait as e:
            logger.warning(f"[STREAM] FloodWait {flood_seconds(e)}s on part {part.id}, waiting")
            await asyncio.sleep(flood_seconds(e))

        except RPCError as e:
            if "FILE_REFERENCE" not in f"{getattr(e, 'ID', '')} {e}":
                raise
            logger.warning(f"[STREAM] File reference expired for part {part.id}, refreshing")
            invalidate_file_id_cache(part.id, client_id=id(client))
            new_file_id = await refresh_file_id(part, client)
            if not new_file_id:
                raise RuntimeError("Failed to refresh expired file reference") from e
            FILE_ID_CACHE[(part.id, id(client))] = (new_file_id, time.time())

        except (OSError, AttributeError, BadMsgNotification) as e:  # TimeoutError is an OSError
            # AttributeError: Pyrogram's session desync (BadMsgNotification) on older paths.
            # The session is never dropped here: a dead connection makes Pyrogram restart it
            # (no data for 10 s while a pong is due every 5), its restart wakes the requests
            # in flight with a TimeoutError, and its start() retries until connected, so
            # stopping it from outside only left zombies reconnecting (measured: ~8x the
            # disconnects). Retrying here waited for it: up to a minute when its restarts
            # kept failing, while the stream's other client was fine.
            if session is not None and not session.is_connected.is_set():
                logger.debug(
                    f"[STREAM] Chunk {index} of part {part.id}: session reconnecting "
                    f"({type(e).__name__})"
                )
                raise SessionDown from e
            logger.warning(
                f"[STREAM] Chunk {index} of part {part.id} failed ({type(e).__name__}: {e}), "
                f"retry {attempt}/{MAX_ATTEMPTS}"
            )
            # Jitter: fetches failing together shouldn't all resend at the same instant
            await asyncio.sleep(random.uniform(0.2, 1.0) * attempt)

    raise RuntimeError(
        f"Failed to fetch chunk {index} of part {part.id} after {MAX_ATTEMPTS} attempts"
    )


async def _pyrogram_chunk(client: Client, file_id: str, index: int) -> bytes:
    """One chunk through Pyrogram's get_file, which opens the media session or follows a
    CDN redirect. It logs and swallows errors, so nothing coming back is raised as an
    OSError for fetch_chunk to retry (with the session now open, on the direct path)."""
    # ponytail: one call per client at a time; a CDN-served file would fetch serially
    async with _open_locks.setdefault(id(client), asyncio.Lock()):
        # Pyrogram annotates stream_media like download_media; it is an async generator
        chunks_gen = client.stream_media(file_id, offset=index, limit=1)
        async with aclosing(chunks_gen) as chunks:  # pyright: ignore[reportArgumentType]
            async for chunk in chunks:
                return chunk
    raise OSError("get_file returned no data")
