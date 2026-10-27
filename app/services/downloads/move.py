"""A download corrected after its upload: its files are copied to their new topic, and the
originals go, with their library titles and their backup copies."""

import asyncio
from itertools import batched

from loguru import logger
from pyrogram import Client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.database import async_session_maker
from app.models.backup import BackupChannel, BackupMessage
from app.models.download import Download
from app.models.media import MediaItem, MediaPart
from app.services.downloads.service import schedule_scan

MOVE_RETRY_SECONDS = 30  # no worker connected (a restart): wait, try again
MOVE_RETRIES = 20
MOVE_FAILED = "Spostamento su Telegram non riuscito"
NO_WORKER = "nessun worker disponibile"

# The running moves, by download; asked again while one runs, it runs once more after
_moves: dict[int, asyncio.Task] = {}
_again: set[int] = set()


async def topic_id_for(client: Client, chat_id: int, topic: str | int) -> int:
    """A title's forum topic, created if missing (as tools/telegram_upload.py does)."""
    if isinstance(topic, int):
        return topic
    async for t in client.get_forum_topics(chat_id):
        if t.name.casefold() == topic.casefold():
            return t.message_thread_id
    created = await client.create_forum_topic(chat_id, topic)
    return created.message_thread_id or created.id


async def _update_file(session: AsyncSession, download_id: int, path: str, **changes) -> None:
    """This file's entry only, on the row as it is now (the agent's sync and a correction
    write the same list), and commit."""
    query = select(Download).where(Download.id == download_id).with_for_update()
    row = (await session.scalars(query.execution_options(populate_existing=True))).one()
    row.files = [{**f, **changes} if f["path"] == path else f for f in row.files]
    await session.commit()


async def _forget(
    session: AsyncSession, chat_id: int, old_ids: list[int], emptied: tuple[set[int], set[int]]
) -> dict[int, list[int]]:
    """Drop the library titles and backup rows of messages that are gone; returns the
    workers' backup copies to delete, by backup chat. The titles' series and franchises go
    into `emptied`: the scan step prunes those it leaves empty."""
    parts = select(MediaPart.media_item_id).where(
        MediaPart.channel_id == chat_id, MediaPart.message_id.in_(old_ids)
    )
    items = (await session.scalars(select(MediaItem).where(MediaItem.id.in_(parts)))).all()
    for item in items:
        if item.series_id:
            emptied[0].add(item.series_id)
        if item.franchise_id:
            emptied[1].add(item.franchise_id)
        await session.delete(item)  # through the ORM: its parts and streams go with it

    rows = await session.execute(
        select(BackupMessage, BackupChannel)
        .join(BackupMessage.backup_channel)
        .where(BackupMessage.main_channel_id == chat_id, BackupMessage.main_message_id.in_(old_ids))
    )
    copies: dict[int, list[int]] = {}
    for row, backup in rows.tuples():
        if backup.archive_account_id is not None:
            row.pending_delete = True  # no worker is in an archive: its account deletes them
            continue
        copies.setdefault(backup.backup_channel_id, []).append(row.backup_message_id)
        await session.delete(row)
    return copies


async def _delete_originals(
    session: AsyncSession,
    client: Client,
    chat_id: int,
    download_id: int,
    path: str,
    ids: list[int],
    emptied: tuple[set[int], set[int]],
) -> None:
    """Telegram first, the database last: a failure leaves `stale_ids` for the next move,
    and deleting a message twice is harmless."""
    await client.delete_messages(chat_id, ids)
    copies = await _forget(session, chat_id, ids, emptied)
    # Left there, a backup promoted to main would bring the old titles back
    for backup_chat_id, copy_ids in copies.items():
        for chunk in batched(copy_ids, 100, strict=False):
            await client.delete_messages(backup_chat_id, list(chunk))
    await _update_file(session, download_id, path, stale_ids=[])


async def move_uploaded(session: AsyncSession, download: Download, client: Client) -> None:
    """Every uploaded file whose topic is not where its messages are is copied there, then
    its originals are deleted; the topics it reached are scanned."""
    chat_id = get_settings().channel_ids_list[0]
    download_id = download.id
    topic_ids: dict[str | int, int] = {}
    moved: set[int] = set()
    emptied: tuple[set[int], set[int]] = (set(), set())  # series, franchises
    try:
        for path in [f["path"] for f in download.files if f["uploaded"]]:
            f = next(f for f in download.files if f["path"] == path)
            if f.get("stale_ids"):  # copied by an earlier move that failed after
                await _delete_originals(
                    session, client, chat_id, download_id, path, f["stale_ids"], emptied
                )
                f = next(f for f in download.files if f["path"] == path)
                moved.add(f["topic_id"])  # scanned again before its old titles are pruned
            if f["topic"] not in topic_ids:
                topic_ids[f["topic"]] = await topic_id_for(client, chat_id, f["topic"])
            topic_id = topic_ids[f["topic"]]
            if topic_id == f["topic_id"]:
                continue
            old_ids = f["message_ids"]
            sent = await client.forward_messages(
                chat_id, chat_id, old_ids, message_thread_id=topic_id, send_copy=True
            )
            new_ids = [m.id for m in (sent if isinstance(sent, list) else [sent])]
            if len(new_ids) != len(old_ids):  # the originals stay: deleting them would lose parts
                raise RuntimeError(f"{path}: {len(new_ids)} of {len(old_ids)} parts copied")
            await _update_file(
                session,
                download_id,
                path,
                topic_id=topic_id,
                message_ids=new_ids,
                stale_ids=old_ids,
            )
            moved.add(topic_id)
            await _delete_originals(session, client, chat_id, download_id, path, old_ids, emptied)
    finally:
        if moved:
            schedule_scan(download_id, sorted(moved), sorted(emptied[0]), sorted(emptied[1]))


async def _move(download_id: int) -> None:
    error = NO_WORKER
    for _ in range(MOVE_RETRIES):
        async with async_session_maker() as session:
            best = await worker_manager.get_best_worker(session)
            if best is not None:
                download = await session.get(Download, download_id)
                if download is None:
                    return
                try:
                    await move_uploaded(session, download, best[1])
                except Exception as e:
                    logger.warning(f"Download {download_id}: move failed: {e}")
                    error = str(e)
                    break
                if download.error and download.error.startswith(MOVE_FAILED):
                    download.error = None  # an earlier failure, finished now
                    await session.commit()
                return
        await asyncio.sleep(MOVE_RETRY_SECONDS)
    async with async_session_maker() as session:
        if download := await session.get(Download, download_id):
            download.error = f"{MOVE_FAILED}: {error}"
            await session.commit()


async def _run(download_id: int) -> None:
    try:
        while True:
            _again.discard(download_id)
            try:
                await _move(download_id)
            except Exception as e:  # the database, say: a later correction asks again
                logger.warning(f"Download {download_id}: move not run: {e}")
            if download_id not in _again:
                return
    finally:
        del _moves[download_id]


def schedule_move(download_id: int) -> None:
    """Move the download's uploaded files in the background, one move per download at a
    time."""
    if download_id in _moves:
        _again.add(download_id)
    else:
        _moves[download_id] = asyncio.create_task(_run(download_id))
