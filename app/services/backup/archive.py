"""Archive accounts: the owners of archive groups, never in the streaming pool.

An archive account goes online only while it works (the day's sync, a creation, a
promotion): its client starts from the saved session and stops at the end, so it makes
a few dozen requests a day, like any user.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from loguru import logger
from pyrogram import Client
from pyrogram.errors import RPCError, UserAlreadyParticipant
from pyrogram.types import ChatPrivileges
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.backup import ArchiveAccount

settings = get_settings()

# The rights promote_admins gives the main group's admins in a backup group
WORKER_RIGHTS = ChatPrivileges(
    can_manage_chat=True,
    can_delete_messages=True,
    can_manage_video_chats=True,
    can_restrict_members=True,
    can_promote_members=True,
    can_change_info=True,
    can_invite_users=True,
    can_pin_messages=True,
    can_manage_topics=True,
)


_busy: dict[int, asyncio.Lock] = {}


@asynccontextmanager
async def archive_client(session: AsyncSession, account: ArchiveAccount) -> AsyncIterator[Client]:
    """The account's client, online for the duration of the block. One block at a time
    per account: two syncs at once would each forward what the other is forwarding."""
    async with _busy.setdefault(account.id, asyncio.Lock()):
        client = Client(
            name=f"archive_{account.id}",
            api_id=settings.api_id,
            api_hash=settings.api_hash,
            session_string=account.session_string,
            in_memory=True,
        )
        await client.start()
        try:
            # As load_workers does: keep the session as Telegram last left it
            updated = await client.export_session_string()
            if updated != account.session_string:
                account.session_string = updated
                await session.commit()
            yield client
        finally:
            await client.stop()


async def chat_ids(client: Client) -> set[int]:
    """The account's chats. Reading them also gives Pyrogram their access hashes, which
    an in-memory session starts without."""
    # Pyrogram annotates its async generators as coroutines
    return {d.chat.id async for d in client.get_dialogs() if d.chat}  # pyright: ignore[reportGeneralTypeIssues]


async def _join(member: Client, chat_id: int, client: Client) -> None:
    """client joins chat_id through a one-use link from member, if it isn't in yet."""
    created = await member.create_chat_invite_link(chat_id, member_limit=1)
    try:
        await client.join_chat(created.invite_link)
    except UserAlreadyParticipant:
        pass


async def join_main(workers: list[Client], archive: Client, main_channel_id: int) -> None:
    """Make the archive account a member of the main group (a new one after a promotion):
    it reads and forwards from there. The invite link comes from the first worker account
    allowed to make one (an admin of that group)."""
    if main_channel_id in await chat_ids(archive):
        return
    refused: list[str] = []
    for worker in workers:
        try:
            await _join(worker, main_channel_id, archive)
        except RPCError as e:
            refused.append(str(e))
            continue
        logger.info(f"[ARCHIVE] Archive account joined the main group {main_channel_id}")
        return
    raise RuntimeError(
        f"No worker account could invite the archive account into {main_channel_id}: "
        + ("; ".join(refused) or "no worker account")
    )


async def let_workers_in(archive: Client, group_id: int, workers: list[Client]) -> None:
    """Before an archive group becomes the main one: each worker account joins it, or
    none could read its files, as an admin, as in the main group (invite links for the
    next archive, topics)."""
    await chat_ids(archive)
    for worker in workers:
        await _join(archive, group_id, worker)
    # Promoting a user takes their access hash, which the account learns by reading them
    # Pyrogram annotates its async generators as coroutines
    async for _ in archive.get_chat_members(group_id):  # pyright: ignore[reportGeneralTypeIssues]
        pass
    for worker in workers:
        me = worker.me or await worker.get_me()  # set by start(), typed optional
        await archive.promote_chat_member(group_id, me.id, privileges=WORKER_RIGHTS)
    logger.info(f"[ARCHIVE] {len(workers)} worker account(s) joined the archive group {group_id}")
