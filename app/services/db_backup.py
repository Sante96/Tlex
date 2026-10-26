"""A copy of TLEX's database once a day: in full on this machine, and without the account
secrets in the backup group on Telegram.

The full copy (db-backups/, the last KEEP days) restores everything. The Telegram copy
outlives this machine but leaves out the worker accounts' Telegram sessions and the
login tokens: whoever can read the group could take those accounts over. After restoring
it, the workers are logged in again from the admin page.

Restore: pg_restore --clean --if-exists -d tlex_db <file>.dump
"""

import asyncio
import os
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_maker
from app.models.backup import BackupChannel

settings = get_settings()

BACKUP_DIR = Path("db-backups")
KEEP = 7
# Account takeover material: Telegram sessions, live login tokens, pending TV logins
SECRET_TABLES = ("workers", "refresh_tokens", "device_codes")
DUMP_TIMEOUT = 300


async def _dump(path: Path, exclude_data: tuple[str, ...] = ()) -> None:
    cmd = [
        "pg_dump",
        "--format=custom",  # compressed, for pg_restore
        "-h",
        settings.postgres_host,
        "-p",
        str(settings.postgres_port),
        "-U",
        settings.postgres_user,
        "-d",
        settings.postgres_db,
        "-f",
        str(path),
        *(f"--exclude-table-data={table}" for table in exclude_data),
    ]
    env = {**os.environ, "PGPASSWORD": settings.postgres_password}
    # A thread, not asyncio's subprocess: the dev backend also runs on Windows
    result = await asyncio.to_thread(
        subprocess.run, cmd, capture_output=True, env=env, timeout=DUMP_TIMEOUT
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip()[-300:])


async def _send(path: Path) -> None:
    """Post the file in the active backup group (its General topic)."""
    from app.core.worker_manager import worker_manager

    async with async_session_maker() as session:
        chat_id = await session.scalar(
            select(BackupChannel.backup_channel_id).where(BackupChannel.is_active).limit(1)
        )
    if chat_id is None:
        logger.info("[DB BACKUP] No backup group: the copy stays on this machine only")
        return
    clients = await worker_manager.get_available_clients(limit=1)
    if not clients:
        raise RuntimeError("no worker free")
    try:
        await clients[0].send_document(
            chat_id, str(path), caption=f"TLEX database {date.today()} (no account secrets)"
        )
        logger.info("[DB BACKUP] Sent to the backup group")
    finally:
        worker_manager.release_clients(clients)


async def backup_database() -> None:
    """Today's copies. A failure is logged: the next day's run tries again."""
    name = f"tlex-{date.today()}.dump"
    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        await _dump(BACKUP_DIR / name)
        for old in sorted(BACKUP_DIR.glob("tlex-*.dump"))[:-KEEP]:
            old.unlink()
        logger.info(f"[DB BACKUP] Saved {name}")

        with tempfile.TemporaryDirectory() as tmp:
            shared = Path(tmp) / name
            await _dump(shared, SECRET_TABLES)
            await _send(shared)
    except Exception as e:
        logger.error(f"[DB BACKUP] Failed: {e}")
