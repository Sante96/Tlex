"""The daily database copy: in full on this machine, without the account secrets on Telegram."""

import subprocess
from datetime import date
from pathlib import Path

import pytest

from app.services import db_backup


@pytest.fixture
def dumps(mocker, tmp_path):
    """pg_dump writes a file per call; returns each call's command line."""
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[cmd.index("-f") + 1]).write_bytes(b"dump")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    mocker.patch.object(db_backup.subprocess, "run", side_effect=run)
    mocker.patch.object(db_backup, "BACKUP_DIR", tmp_path)
    return calls


async def test_the_full_copy_stays_here_the_one_without_secrets_goes_to_telegram(dumps, mocker):
    sent = []
    mocker.patch.object(db_backup, "_send", side_effect=lambda path: sent.append(path.exists()))

    await db_backup.backup_database()

    local, shared = dumps
    assert not any(arg.startswith("--exclude-table-data") for arg in local)
    for table in ("workers", "refresh_tokens", "device_codes"):
        assert f"--exclude-table-data={table}" in shared
    assert sent == [True]
    assert [p.name for p in db_backup.BACKUP_DIR.iterdir()] == [f"tlex-{date.today()}.dump"]


async def test_the_last_seven_days_are_kept(dumps, mocker):
    mocker.patch.object(db_backup, "_send")
    for day in range(1, 10):
        (db_backup.BACKUP_DIR / f"tlex-2020-01-0{day}.dump").write_bytes(b"old")

    await db_backup.backup_database()

    kept = sorted(p.name for p in db_backup.BACKUP_DIR.iterdir())
    assert kept == [f"tlex-2020-01-0{day}.dump" for day in range(4, 10)] + [
        f"tlex-{date.today()}.dump"
    ]


async def test_a_failed_telegram_copy_keeps_the_local_one(dumps, mocker):
    mocker.patch.object(db_backup, "_send", side_effect=RuntimeError("no worker free"))

    await db_backup.backup_database()  # logged, not raised: the scheduler goes on

    assert (db_backup.BACKUP_DIR / f"tlex-{date.today()}.dump").exists()
