"""A scan reads every topic whole, and waits out Telegram's flood waits.

Since the move to the VPS each 3-hourly scan hit FLOOD_WAIT (~29 s) on a topic, logged it
as an error and went on: the wait still running, the next 35 topics failed the same way,
and what the seedbox uploaded there never reached the library. And a scan read only each
topic's latest 100 messages: a bulk upload of more than that between two scans left the
older files out for good.
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

from pyrogram.errors import FloodWait

from app.services.scanner.service import ScannerService


async def test_a_flood_wait_is_waited_out_not_skipped(mocker):
    service = ScannerService()
    service._scanner = MagicMock(
        scan_channel=AsyncMock(side_effect=[FloodWait(value=29), []]),
        group_files=MagicMock(return_value=[]),
    )
    sleep = mocker.patch("app.services.scanner.service.asyncio.sleep", new=AsyncMock())
    stats = {"files_found": 0, "topics": 0, "media_created": 0, "errors": []}

    await service._scan_topic(AsyncMock(), MagicMock(), -100, 36, 0, stats, topic_name="Show")

    sleep.assert_awaited_once_with(30)
    assert service._scanner.scan_channel.await_count == 2
    assert stats["topics"] == 1 and stats["errors"] == []


async def test_a_scan_reads_each_topic_whole(mocker):
    from app.config import Settings
    from app.core.worker_manager import worker_manager

    mocker.patch.object(Settings, "channel_ids_list", new_callable=PropertyMock, return_value=[-100])
    mocker.patch.object(
        worker_manager, "get_best_worker", new=AsyncMock(return_value=(MagicMock(), MagicMock()))
    )
    service = ScannerService()
    topics = mocker.patch.object(service, "_scan_all_topics", new=AsyncMock())

    await service.scan_all_channels(AsyncMock())  # as the scheduler and the scan button call it

    assert topics.await_args.args[3] == 0  # limit 0: every message, not the latest 100
