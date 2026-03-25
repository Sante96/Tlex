"""Telegram API helpers for streaming (peer cache, file_id refresh)."""

import time

from loguru import logger
from pyrogram import Client

from app.models.media import MediaPart
from app.services.streaming.cache import _FILE_ID_CACHE, _FILE_ID_CACHE_TTL
from app.services.streaming.crash_log import flush as crash_flush
from app.services.streaming.crash_log import record as crash_record


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


async def _fetch_file_id_from_channel(
    client: Client, channel_id: int, message_id: int
) -> str | None:
    """Fetch file_id from a specific channel/message pair."""
    import asyncio

    messages = await asyncio.wait_for(
        client.get_messages(chat_id=channel_id, message_ids=message_id),
        timeout=10.0,
    )
    if not messages:
        return None
    message = messages if not isinstance(messages, list) else messages[0]
    doc = message.document or message.video
    return doc.file_id if doc else None


async def refresh_file_id(part: MediaPart, client: Client) -> str | None:
    """
    Refresh expired file_id by fetching the original message.
    Falls back to the backup channel if the main channel is unavailable.

    NOTE: Does NOT update DB to avoid race conditions during parallel streaming.
    The file_id is only cached in memory. DB will be updated during next scan.
    """
    crash_record("refresh_file_id.attempt", part_id=part.id, part_index=part.part_index)

    # --- Primary: fetch from main channel ---
    try:
        logger.debug(f"Refreshing file_id for part {part.part_index}")
        new_file_id = await _fetch_file_id_from_channel(client, part.channel_id, part.message_id)
        if new_file_id:
            part.telegram_file_id = new_file_id
            logger.debug(f"Refreshed file_id for part {part.part_index}")
            crash_record("refresh_file_id.ok", part_id=part.id, source="primary")
            return new_file_id
        logger.error(f"No document in message {part.message_id}")
        crash_record("refresh_file_id.no_doc", part_id=part.id, message_id=part.message_id)
    except Exception as e:
        crash_record("refresh_file_id.primary_error", part_id=part.id, error=str(e))
        logger.warning(
            f"Failed to refresh file_id from main channel for part {part.part_index}: {e}"
        )

    # --- Fallback: try backup channel ---
    try:
        from app.services.backup.service import backup_service

        loc = await backup_service.get_fallback_location(part.channel_id, part.message_id)
        if loc:
            backup_channel_id, backup_message_id = loc
            logger.info(
                f"[BACKUP] Trying backup channel {backup_channel_id} "
                f"msg={backup_message_id} for part {part.part_index}"
            )
            fallback_file_id = await _fetch_file_id_from_channel(
                client, backup_channel_id, backup_message_id
            )
            if fallback_file_id:
                part.telegram_file_id = fallback_file_id
                logger.info(f"[BACKUP] Fallback file_id obtained for part {part.part_index}")
                crash_record("refresh_file_id.ok", part_id=part.id, source="backup")
                return fallback_file_id
            logger.error(f"[BACKUP] No document in backup message {backup_message_id}")
            crash_record("refresh_file_id.no_doc", part_id=part.id, source="backup")
        else:
            logger.debug(f"No backup mapping found for channel={part.channel_id} msg={part.message_id}")
    except Exception as e:
        crash_record("refresh_file_id.backup_error", part_id=part.id, error=str(e))
        logger.error(f"[BACKUP] Fallback refresh failed for part {part.part_index}: {e}")

    # Both channels failed — flush diagnostics so the crash dump captures the context
    crash_flush(reason=f"refresh_file_id failed for part {part.id}")
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
        crash_record("refresh_all.no_clients", parts=len(parts))
        return

    now = time.time()
    client = clients[0]
    client_id = id(client)

    crash_record("refresh_all.start", parts=len(parts), client_id=client_id)

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
        crash_record("refresh_all.cache_hit", parts=len(parts))
        return

    await populate_peer_cache(client, parts)

    failed_parts = []
    for part in parts:
        cache_key = (part.id, client_id)
        cached = _FILE_ID_CACHE.get(cache_key)
        if cached and (now - cached[1]) <= _FILE_ID_CACHE_TTL:
            part.telegram_file_id = cached[0]
            continue
        new_file_id = await refresh_file_id(part, client)
        if new_file_id:
            _FILE_ID_CACHE[cache_key] = (new_file_id, now)
        else:
            failed_parts.append(part.id)

    if failed_parts:
        crash_record("refresh_all.partial_failure", failed_part_ids=failed_parts)
        crash_flush(reason=f"refresh_all_file_ids: {len(failed_parts)} part(s) failed")
    else:
        crash_record("refresh_all.done", parts=len(parts))


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

    failed_parts = []
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
        crash_record("ensure_file_ids.refresh", part_id=part.id, client_id=client_id)
        new_file_id = await refresh_file_id(part, client)
        if new_file_id:
            _FILE_ID_CACHE[cache_key] = (new_file_id, now)
        else:
            failed_parts.append(part.id)

    if failed_parts:
        crash_record("ensure_file_ids.failure", failed_part_ids=failed_parts, client_id=client_id)
        crash_flush(reason=f"ensure_file_ids_for_client: {len(failed_parts)} part(s) failed")
