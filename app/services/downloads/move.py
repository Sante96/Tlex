"""A download corrected after its upload: its files are copied to their new topic, and the
originals go, with their library titles and their backup copies."""

from pyrogram import Client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.backup import BackupChannel, BackupMessage
from app.models.download import Download
from app.models.media import MediaItem, MediaPart
from app.services.downloads.service import schedule_scan


async def topic_id_for(client: Client, chat_id: int, topic: str | int) -> int:
    """A title's forum topic, created if missing (as tools/telegram_upload.py does)."""
    if isinstance(topic, int):
        return topic
    async for t in client.get_forum_topics(chat_id):
        if t.name.casefold() == topic.casefold():
            return t.message_thread_id
    created = await client.create_forum_topic(chat_id, topic)
    return created.message_thread_id or created.id


async def _forget(session: AsyncSession, chat_id: int, old_ids: list[int]) -> dict[int, list[int]]:
    """Drop the library titles and backup rows of messages that are gone; returns the
    workers' backup copies to delete, by backup chat."""
    parts = select(MediaPart.media_item_id).where(
        MediaPart.channel_id == chat_id, MediaPart.message_id.in_(old_ids)
    )
    for item in (await session.scalars(select(MediaItem).where(MediaItem.id.in_(parts)))).all():
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


async def move_uploaded(session: AsyncSession, download: Download, client: Client) -> None:
    """Every uploaded file whose topic is not where its messages are moves there, then the
    new topics are scanned."""
    chat_id = get_settings().channel_ids_list[0]
    topic_ids: dict[str | int, int] = {}
    moved: set[int] = set()
    for f in list(download.files):
        if not f["uploaded"]:
            continue
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
            raise RuntimeError(f"{f['path']}: {len(new_ids)} of {len(old_ids)} parts copied")
        download.files = [
            {**g, "topic_id": topic_id, "message_ids": new_ids} if g["path"] == f["path"] else g
            for g in download.files
        ]
        await session.commit()  # the copies exist: their ids must outlive a failure below
        await client.delete_messages(chat_id, old_ids)
        copies = await _forget(session, chat_id, old_ids)
        await session.commit()
        # Left there, a backup promoted to main would bring the old titles back
        for backup_chat_id, ids in copies.items():
            await client.delete_messages(backup_chat_id, ids)
        moved.add(topic_id)
    if moved:
        schedule_scan(download.id, sorted(moved))
