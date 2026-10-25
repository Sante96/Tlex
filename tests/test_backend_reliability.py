"""Regression checks for backend reliability fixes: scanner rollback, scheduler ticks,
watch-progress races, worker removal and backup promotion."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from app.core.worker_manager import WorkerManager
from app.services.backup import backup_service
from app.services.scheduler import AutoScanScheduler

# ---------------------------------------------------------------------------
# Scanner: one bad group must not poison the rest of the scan
# ---------------------------------------------------------------------------


async def test_failed_group_is_rolled_back_and_scan_continues(mocker):
    from app.services.scanner.service import ScannerService

    service = ScannerService()
    service._scanner = MagicMock(
        scan_channel=AsyncMock(return_value=[]),
        group_files=MagicMock(return_value=[MagicMock(base_name="bad"), MagicMock(base_name="ok")]),
    )
    mocker.patch(
        "app.services.scanner.service.process_group",
        new=AsyncMock(side_effect=[RuntimeError("DataError"), MagicMock()]),
    )
    session = AsyncMock()
    stats = {"files_found": 0, "topics": 0, "media_created": 0, "errors": []}

    await service._scan_topic(session, MagicMock(), 1, 2, 10, stats)

    session.rollback.assert_awaited_once()
    assert stats["media_created"] == 1


# ---------------------------------------------------------------------------
# Auto-scan scheduler: due-ness comes from the last run stored in Redis
# ---------------------------------------------------------------------------


async def _one_tick(mocker, last_run: datetime) -> tuple[AutoScanScheduler, AsyncMock]:
    scheduler = AutoScanScheduler()
    redis = AsyncMock()
    redis.get.return_value = str(last_run.timestamp())
    mocker.patch.object(scheduler, "get_interval_hours", new=AsyncMock(return_value=1))
    mocker.patch.object(scheduler, "_get_redis", new=AsyncMock(return_value=redis))
    run = mocker.patch.object(scheduler, "_run_scan", new=AsyncMock())

    async def stop_after_tick(_seconds):
        scheduler._running = False

    mocker.patch("app.services.scheduler.asyncio.sleep", new=stop_after_tick)
    await scheduler.start()
    return scheduler, run


async def test_scan_runs_when_last_run_is_older_than_interval(mocker):
    _, run = await _one_tick(mocker, datetime.now() - timedelta(hours=2))
    run.assert_awaited_once()


async def test_scan_waits_when_last_run_is_recent(mocker):
    last = datetime.now() - timedelta(minutes=10)
    scheduler, run = await _one_tick(mocker, last)
    run.assert_not_awaited()
    assert scheduler.next_scan is not None
    assert abs((scheduler.next_scan - (last + timedelta(hours=1))).total_seconds()) < 1


# ---------------------------------------------------------------------------
# Watch progress: a concurrent insert must not create a duplicate row
# ---------------------------------------------------------------------------


async def test_concurrent_progress_insert_updates_the_existing_row(test_session):
    from app.api.v1.progress import ProgressUpdate, update_progress
    from app.models import MediaItem, User, WatchProgress
    from app.models.media import MediaType

    user = User(email="u@example.com", password_hash="x")
    media = MediaItem(title="M", media_type=MediaType.MOVIE)
    test_session.add_all([user, media])
    await test_session.commit()
    # The other request's row exists, but our SELECT ran before it committed
    test_session.add(
        WatchProgress(user_id=user.id, media_item_id=media.id, position_seconds=10, duration_seconds=100)
    )
    await test_session.commit()

    real_execute = test_session.execute
    calls = {"n": 0}

    async def execute(stmt, *args, **kwargs):
        calls["n"] += 1
        result = await real_execute(stmt, *args, **kwargs)
        if calls["n"] == 2:  # 1: media lookup, 2: progress lookup
            return MagicMock(scalar_one_or_none=lambda: None)
        return result

    test_session.execute = execute
    resp = await update_progress(
        media.id, ProgressUpdate(position_seconds=50, duration_seconds=100), db=test_session, current_user=user
    )

    rows = (await real_execute(select(WatchProgress))).scalars().all()
    assert resp.position_seconds == 50
    assert [r.position_seconds for r in rows] == [50]


# ---------------------------------------------------------------------------
# Worker removal: only that worker's clients stop
# ---------------------------------------------------------------------------


async def test_remove_worker_leaves_other_workers_running():
    manager = WorkerManager()
    a1, a2, b1 = AsyncMock(), AsyncMock(), AsyncMock()
    manager._client_pool = [(1, a1), (1, a2), (2, b1)]
    manager._clients = {1: a1, 2: b1}
    manager._client_in_use = {id(a1): True, id(a2): False, id(b1): True}

    await manager.remove_worker(1)

    assert manager._client_pool == [(2, b1)]
    assert manager._clients == {2: b1}
    a1.stop.assert_awaited_once()
    b1.stop.assert_not_awaited()
    manager.release_clients([a1])  # a stream still holding a removed client
    assert manager._client_in_use == {id(b1): True}


# ---------------------------------------------------------------------------
# Backup promotion: parts must point at the forwarded copies
# ---------------------------------------------------------------------------


async def test_promote_remaps_message_and_topic_ids(test_session, mocker):
    from app.models.backup import BackupChannel, BackupMessage
    from app.models.media import MediaItem, MediaPart, MediaType

    backup = BackupChannel(main_channel_id=-100, backup_channel_id=-200, title="B", topic_map={"7": 70})
    media = MediaItem(title="M", media_type=MediaType.MOVIE)
    test_session.add_all([backup, media])
    await test_session.flush()

    def part(index: int, message_id: int) -> MediaPart:
        return MediaPart(
            media_item_id=media.id, telegram_file_id="f", part_index=index, start_byte=0,
            end_byte=10, file_size=10, channel_id=-100, topic_id=7, message_id=message_id,
        )

    synced, unsynced = part(0, 5), part(1, 6)
    test_session.add_all([
        synced,
        unsynced,
        BackupMessage(
            backup_channel_db_id=backup.id, main_channel_id=-100, main_message_id=5, backup_message_id=55
        ),
    ])
    await test_session.commit()
    mocker.patch.object(backup_service, "create_backup_channel", new=AsyncMock(return_value=MagicMock(id=9)))

    await backup_service.promote_to_main(test_session, MagicMock(), backup)

    assert (synced.channel_id, synced.message_id, synced.topic_id) == (-200, 55, 70)
    assert (unsynced.channel_id, unsynced.message_id) == (-100, 6)


# -- the pool spreads streams over accounts (each account has its own speed cap) --


def _pool(manager: WorkerManager, sizes: dict[int, int]) -> dict[int, list]:
    clients = {wid: [MagicMock(name=f"w{wid}c{i}") for i in range(n)] for wid, n in sizes.items()}
    for wid, cs in clients.items():
        for c in cs:
            manager._client_pool.append((wid, c))
            manager._client_in_use[id(c)] = False
    return clients


async def test_second_client_of_a_stream_comes_from_another_account():
    manager = WorkerManager()
    clients = _pool(manager, {10: 4, 12: 6})

    [first] = await manager.get_available_clients(limit=1)
    second = await manager.try_acquire_one(spread_from=[first])

    assert first in clients[10]
    assert second in clients[12]


async def test_new_streams_start_on_the_least_busy_account():
    manager = WorkerManager()
    clients = _pool(manager, {10: 4, 12: 6})
    for c in clients[10][:2]:
        manager._client_in_use[id(c)] = True

    [client] = await manager.get_available_clients(limit=1)
    assert client in clients[12]


async def test_same_account_when_no_other_has_free_clients():
    manager = WorkerManager()
    clients = _pool(manager, {10: 2, 12: 1})
    manager._client_in_use[id(clients[12][0])] = True

    first = clients[10][0]
    manager._client_in_use[id(first)] = True
    assert await manager.try_acquire_one(spread_from=[first]) is clients[10][1]
    assert await manager.try_acquire_one(spread_from=[first]) is None


# -- Pyrogram tuning (plain transport, linear recv, more crypto threads) --


async def test_tcp_recv_joins_reads_and_stops_on_eof():
    from pyrogram.connection.transport.tcp import TCP

    from app.core.pyrogram_tuning import _recv

    class Reader:
        def __init__(self, *pieces):
            self.pieces = list(pieces)

        async def read(self, n):
            return self.pieces.pop(0)[:n] if self.pieces else b""

    tcp = MagicMock(spec=TCP)
    tcp.reader = Reader(b"ab", b"cde", b"f")
    assert await _recv(tcp, 6) == b"abcdef"
    tcp.reader = Reader(b"ab")
    assert await _recv(tcp, 6) is None  # connection closed mid-message


def test_apply_switches_transport_and_crypto_threads(monkeypatch):
    import pyrogram
    from pyrogram.connection.transport.tcp import TCP, TCPAbridged
    from pyrogram.session import session as session_module

    from app.core import pyrogram_tuning

    # restored after the test
    monkeypatch.setattr(session_module, "Connection", session_module.Connection)
    monkeypatch.setattr(TCP, "recv", TCP.recv)
    monkeypatch.setattr(pyrogram, "crypto_executor", pyrogram.crypto_executor)

    pyrogram_tuning.apply()

    assert session_module.Connection(2, False, False, {}, True).mode is TCPAbridged
    assert TCP.recv is pyrogram_tuning._recv
    assert pyrogram.crypto_executor._max_workers == pyrogram_tuning.CRYPTO_THREADS
