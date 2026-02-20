"""Telegram chunk download with retry logic."""

import asyncio
from collections.abc import AsyncIterator, Callable

from loguru import logger
from pyrogram import Client
from pyrogram.errors import FileReferenceExpired, FloodWait, RPCError

from app.models.media import MediaPart
from app.services.streaming.cache import (
    PYROGRAM_CHUNK_SIZE,
    _cache_chunk,
    _get_cached_chunk,
    invalidate_file_id_cache,
)
from app.services.streaming.telegram import refresh_file_id


async def stream_part(
    client: Client,
    part: MediaPart,
    offset: int,
    length: int,
    *,
    is_force_released: Callable[[], bool],
) -> AsyncIterator[bytes]:
    """
    Stream bytes from a single part with retry logic.

    Handles FileReferenceExpired by refreshing file_id and resuming from
    the last successfully downloaded chunk position.
    """
    if not client:
        raise RuntimeError("No client provided")

    max_retries = 5
    bytes_yielded = 0
    file_id = part.telegram_file_id

    initial_chunk_offset = offset // PYROGRAM_CHUNK_SIZE
    initial_skip_bytes = offset % PYROGRAM_CHUNK_SIZE

    # Calculate total chunks needed
    total_chunks_needed = (length + initial_skip_bytes + PYROGRAM_CHUNK_SIZE - 1) // PYROGRAM_CHUNK_SIZE

    logger.info(
        f"[STREAM] Part {part.part_index}: offset={offset}, len={length}, chunks={total_chunks_needed}"
    )

    # Phase 1: Serve from cache
    cache_hits = 0
    skip_bytes = initial_skip_bytes
    for idx in range(initial_chunk_offset, initial_chunk_offset + total_chunks_needed):
        cached = _get_cached_chunk(part.id, idx)
        if cached:
            cache_hits += 1
            chunk = cached

            if skip_bytes > 0:
                if len(chunk) <= skip_bytes:
                    skip_bytes -= len(chunk)
                    continue
                chunk = chunk[skip_bytes:]
                skip_bytes = 0

            if not chunk:
                continue

            chunk_len = len(chunk)
            if bytes_yielded + chunk_len > length:
                needed = length - bytes_yielded
                yield chunk[:needed]
                bytes_yielded += needed
            else:
                yield chunk
                bytes_yielded += chunk_len

            if bytes_yielded >= length:
                if cache_hits > 0:
                    logger.debug(f"Served {cache_hits} chunks from cache")
                return
        else:
            break

    if bytes_yielded >= length:
        if cache_hits > 0:
            logger.debug(f"Served {cache_hits} chunks from cache (complete)")
        return

    # Phase 2: Fetch remaining chunks from Telegram with retry
    next_chunk_to_fetch = initial_chunk_offset + cache_hits
    chunks_remaining = total_chunks_needed - cache_hits
    skip_bytes_for_fetch = initial_skip_bytes if cache_hits == 0 else 0

    if cache_hits > 0:
        logger.debug(f"Cache hit: {cache_hits} chunks, fetching {chunks_remaining} more")

    attempt = 0
    consecutive_failures = 0
    max_consecutive_failures = 3

    # Per-chunk timeout: Pyrogram's GetFile can hang for 5 retries × 15s = 75s
    # before raising OSError. We abort each chunk after 20s to fail fast.
    CHUNK_TIMEOUT = 20.0

    while attempt < max_retries:
        try:
            chunks_fetched_this_attempt = 0
            stream_iter = client.stream_media(
                file_id,
                offset=next_chunk_to_fetch,
                limit=chunks_remaining,
            ).__aiter__()

            while True:
                # Bail out if force-released
                if is_force_released():
                    logger.info("[STREAM] Aborting stream_part: reader was force-released")
                    return

                try:
                    chunk = await asyncio.wait_for(
                        stream_iter.__anext__(), timeout=CHUNK_TIMEOUT
                    )
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    raise OSError(
                        f"Chunk fetch timeout after {CHUNK_TIMEOUT}s — stale media session"
                    ) from None

                # Cache the chunk
                _cache_chunk(part.id, next_chunk_to_fetch, chunk)
                chunks_fetched_this_attempt += 1

                # Update position for potential resume
                next_chunk_to_fetch += 1
                chunks_remaining -= 1

                # Handle skip bytes for first chunk
                if skip_bytes_for_fetch > 0:
                    if len(chunk) <= skip_bytes_for_fetch:
                        skip_bytes_for_fetch -= len(chunk)
                        continue
                    chunk = chunk[skip_bytes_for_fetch:]
                    skip_bytes_for_fetch = 0

                if not chunk:
                    continue

                chunk_len = len(chunk)
                if bytes_yielded + chunk_len > length:
                    needed = length - bytes_yielded
                    yield chunk[:needed]
                    bytes_yielded += needed
                    return
                else:
                    yield chunk
                    bytes_yielded += chunk_len

                if bytes_yielded >= length:
                    return

            # Check if we got all expected chunks
            if chunks_remaining > 0:
                consecutive_failures += 1
                wait_time = 1.0 * consecutive_failures
                logger.warning(
                    f"[INCOMPLETE] Stream ended early for part {part.id}: "
                    f"got {chunks_fetched_this_attempt} chunks this attempt, "
                    f"{chunks_remaining} remaining (failure {consecutive_failures}/{max_consecutive_failures})"
                )

                if consecutive_failures >= max_consecutive_failures:
                    await _handle_consecutive_failures(
                        part, client, file_id, wait_time, consecutive_failures
                    )
                    file_id = part.telegram_file_id  # May have been updated
                    consecutive_failures = 0
                    attempt += 1
                    continue
                else:
                    await asyncio.sleep(wait_time)
                    continue

            # Successfully completed
            return

        except RPCError as e:
            file_id = await _handle_rpc_error(e, part, client, file_id, next_chunk_to_fetch, attempt, max_retries)
            attempt += 1

        except AttributeError as e:
            if "BadMsgNotification" in str(e) or "bytes" in str(e):
                attempt += 1
                if attempt < max_retries:
                    wait_time = 0.5 * attempt
                    logger.warning(f"Session desync, retry {attempt}/{max_retries} in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
            else:
                raise

        except TimeoutError:
            attempt += 1
            if attempt < max_retries:
                wait_time = attempt * 2
                logger.warning(f"Timeout, retry {attempt}/{max_retries} in {wait_time}s")
                await asyncio.sleep(wait_time)
                continue
            else:
                raise

        except OSError as e:
            attempt += 1
            if attempt < max_retries:
                # Drop all stale media sessions so Pyrogram recreates them fresh on retry.
                # The session object stays in media_sessions after idle TCP timeout,
                # causing every subsequent get_file to fail on the broken connection.
                media_sessions = getattr(client, "media_sessions", {})
                for dc_id in list(media_sessions.keys()):
                    try:
                        await media_sessions[dc_id].stop()
                    except Exception:
                        pass
                    media_sessions.pop(dc_id, None)
                    logger.debug(f"Dropped stale media session DC{dc_id} for client {id(client)}")
                # First attempt: retry immediately (minimize video stutter)
                # Subsequent attempts: backoff
                if attempt > 1:
                    wait_time = min(attempt * 2, 8)
                    logger.warning(
                        f"Connection error ({e}), retry {attempt}/{max_retries} in {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.warning(
                        f"Connection error ({e}), retry {attempt}/{max_retries} immediately — dropped stale media session"
                    )
                continue
            else:
                raise

        except Exception as e:
            logger.error(f"Unexpected error streaming part {part.id}: {type(e).__name__}: {e}")
            raise

    logger.error(f"Exhausted all {max_retries} retries for part {part.id}")
    raise RuntimeError(f"Failed to stream part {part.id} after {max_retries} retries")


async def _handle_consecutive_failures(
    part: MediaPart,
    client: Client,
    file_id: str,
    wait_time: float,
    consecutive_failures: int,
) -> None:
    """Handle too many consecutive stream failures by refreshing file_id."""
    logger.warning(
        f"[REFRESH] {consecutive_failures} consecutive failures, "
        f"refreshing file_id for part {part.id}"
    )
    await asyncio.sleep(wait_time)
    invalidate_file_id_cache(part.id, client_id=id(client))
    new_file_id = await refresh_file_id(part, client)
    if new_file_id:
        logger.info(f"[REFRESH] Got new file_id for part {part.id}, retrying")
    else:
        logger.error("Failed to refresh file_id")
        raise RuntimeError("Failed to refresh expired file reference")


async def _handle_rpc_error(
    e: RPCError,
    part: MediaPart,
    client: Client,
    file_id: str,
    next_chunk: int,
    attempt: int,
    max_retries: int,
) -> str:
    """Handle RPCError during streaming, return (possibly refreshed) file_id."""
    logger.warning(f"[RETRY] Caught RPCError at chunk {next_chunk}: {type(e).__name__}")

    is_expired = isinstance(e, FileReferenceExpired)
    if not is_expired:
        err_str = str(e)
        err_id = getattr(e, "ID", "")
        if "FILE_REFERENCE" in err_id or "FILE_REFERENCE" in err_str:
            is_expired = True

    if is_expired:
        logger.warning(
            f"FileReferenceExpired for part {part.id}, attempt {attempt + 1}/{max_retries}"
        )
        invalidate_file_id_cache(part.id, client_id=id(client))
        new_file_id = await refresh_file_id(part, client)
        if new_file_id:
            logger.info(f"Refreshed file_id, resuming from chunk {next_chunk}")
            return new_file_id
        else:
            raise RuntimeError("Failed to refresh expired file reference") from e

    if isinstance(e, FloodWait):
        logger.warning(f"FloodWait {e.value}s, waiting...")
        await asyncio.sleep(e.value)
        return file_id

    raise
