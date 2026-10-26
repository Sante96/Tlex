"""A file in parts is imported only once all its parts are in the topic.

A scan reads the topic's latest messages: during an upload, or with a message limit that
cuts a group, it saw part of a file. It made a title of it (Avatar: 4 GB of 42), and the
file never grew whole: a title is known by its first part.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.scanner.models import MediaGroup, ScannedFile

GB = 1_000_000_000


def _group(*parts: tuple[int | None, int]) -> MediaGroup:
    return MediaGroup(
        base_name="Avatar.mkv",
        files=[
            ScannedFile(
                message_id=100 + i,
                file_id=f"f{i}",
                file_name="Avatar.mkv" if index is None else f"Avatar.mkv.{index + 1:03d}",
                file_size=size,
                base_name="Avatar.mkv",
                channel_id=-100,
                split_index=index,
            )
            for i, (index, size) in enumerate(parts)
        ],
    )


@pytest.mark.parametrize(
    "parts, complete",
    [
        ([(None, 3 * GB)], True),  # a whole file
        ([(0, 4 * GB), (1, 4 * GB), (2, 2 * GB)], True),  # the last part is the remainder
        ([(0, 4 * GB), (1, 4 * GB)], False),  # all full-size: more to come
        ([(0, 4 * GB)], False),  # the first part alone (the Avatar case)
        ([(1, 4 * GB), (2, 2 * GB)], False),  # the first part outside the scan
        ([(0, 4 * GB), (2, 2 * GB)], False),  # a part missing in the middle
    ],
)
def test_a_group_is_complete_only_with_all_its_parts(parts, complete):
    assert _group(*parts).complete is complete


async def test_an_incomplete_group_waits_for_a_later_scan(mocker):
    from app.services.scanner.service import ScannerService

    whole = _group((None, 3 * GB))
    half = _group((0, 4 * GB), (1, 4 * GB))
    service = ScannerService()
    service._scanner = MagicMock(
        scan_channel=AsyncMock(return_value=[]), group_files=MagicMock(return_value=[half, whole])
    )
    process = mocker.patch(
        "app.services.scanner.service.process_group", new=AsyncMock(return_value=MagicMock())
    )
    stats = {"files_found": 0, "topics": 0, "media_created": 0, "errors": []}

    await service._scan_topic(AsyncMock(), MagicMock(), 1, 99, 10, stats, topic_name="Film")

    assert [call.args[1] for call in process.await_args_list] == [whole]
    assert stats["media_created"] == 1
