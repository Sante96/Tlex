"""Telegram API helpers for streaming (peer cache, file_id refresh)."""

import time

from loguru import logger
from pyrogram import Client

from app.models.media import MediaPart
from app.services.streaming.cache import _FILE_ID_CACHE, _FILE_ID_CACHE_TTL


async def populate_peer_cache(client: Client, parts: list[MediaPart]) -> None:
    """Populate Pyrogram peer cache for the channels containing the parts."""
    channel_ids = {p.channel_id for p in parts}

    for channel_id in channel_ids:
        logger.debug(f"Ensuring peer knowledge for channel {channel_id}")
        try:
            # Fast path: direct lookup (fetches if needed, uses cache if available)
            await client.get_chat(channel_id)
            continue
        except Exception as e:
            logger.debug(f"get_chat({channel_id}) failed: {e}. Falling back to dialogs scan.")

        # Slow path: iterate dialogs
        try:
            found = False
            async for dialog in client.get_dialogs():
                if dialog.chat and dialog.chat.id == channel_id:
                    logger.debug(f"Found channel {channel_id} in dialogs cache")
                    found = True
                    break
            if not found:
                logger.warning(f"Channel {channel_id} not found in dialogs")
        except Exception as e:
            logger.warning(f"Failed to populate peer cache via dialogs: {e}")


async def refresh_file_id(part: MediaPart, client: Client) -> str | None:
    """
    Refresh expired file_id by fetching the original message.

    NOTE: Does NOT update DB to avoid race conditions during parallel streaming.
    The file_id is only cached in memory. DB will be updated during next scan.
    """
    try:
        import asyncio

        logger.debug(f"Refreshing file_id for part {part.part_index}")

        messages = await asyncio.wait_for(
            client.get_messages(
                chat_id=part.channel_id,
                message_ids=part.message_id,
            ),
            timeout=10.0,
        )

        if not messages:
            logger.error(f"Message {part.message_id} not found")
            return None

        message = messages if not isinstance(messages, list) else messages[0]
        doc = message.document or message.video

        if not doc:
            logger.error(f"No document in message {part.message_id}")
            return None

        new_file_id = doc.file_id

        # Only update in-memory, no DB operations to avoid race conditions
        part.telegram_file_id = new_file_id
        logger.debug(f"Refreshed file_id for part {part.part_index}")
        return new_file_id

    except Exception as e:
        logger.error(f"Failed to refresh file_id for part {part.part_index}: {e}")
        return None


async def refresh_all_file_ids(
    clients: list[Client], parts: list[MediaPart]
) -> None:
    """
    Pre-refresh all file_ids to prevent FileReferenceExpired during streaming.

    Writes cache entries keyed by (part.id, client_id) so that
    ensure_file_ids_for_client finds them without re-fetching from Telegram.
    """
    if not clients:
        logger.warning("No clients available for file_id refresh")
        return

    now = time.time()
    client = clients[0]
    client_id = id(client)

    # Check if any part needs refresh for the primary client
    needs_refresh = False
    for part in parts:
        cache_key = (part.id, client_id)
        cached = _FILE_ID_CACHE.get(cache_key)
        if cached is None:
            logger.debug(f"Part {part.id} not in cache, needs refresh")
            needs_refresh = True
            break
        elif (now - cached[1]) > _FILE_ID_CACHE_TTL:
            logger.debug(
                f"Part {part.id} cache expired (age={(now - cached[1]):.0f}s), needs refresh"
            )
            needs_refresh = True
            break
        else:
            part.telegram_file_id = cached[0]

    if not needs_refresh:
        logger.info("[STREAM] All file_ids cached, skipping refresh")
        return

    await populate_peer_cache(client, parts)

    for part in parts:
        cache_key = (part.id, client_id)
        cached = _FILE_ID_CACHE.get(cache_key)
        if cached and (now - cached[1]) <= _FILE_ID_CACHE_TTL:
            part.telegram_file_id = cached[0]
            continue
        new_file_id = await refresh_file_id(part, client)
        if new_file_id:
            _FILE_ID_CACHE[cache_key] = (new_file_id, now)


async def ensure_file_ids_for_client(
    parts: list[MediaPart], client: Client
) -> None:
    """
    Ensure all parts have valid file_ids for the specified client.

    Since file_reference is session-specific in Telegram, each client needs
    its own refresh. This is called proactively before streaming to avoid
    FileReferenceExpired errors during the stream.
    """
    client_id = id(client)

    for part in parts:
        cache_key = (part.id, client_id)

        # Check if we have a recent file_id for this client+part combo
        cached = _FILE_ID_CACHE.get(cache_key)
        now = time.time()

        if cached and (now - cached[1]) <= _FILE_ID_CACHE_TTL:
            part.telegram_file_id = cached[0]
            continue

        # Need to refresh for this client
        logger.debug(f"Refreshing file_id for part {part.part_index} (client {client_id})")
        new_file_id = await refresh_file_id(part, client)
        if new_file_id:
            _FILE_ID_CACHE[cache_key] = (new_file_id, now)
