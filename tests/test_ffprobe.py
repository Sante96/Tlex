"""Scan-time probing reads the head of a file, more only when the header isn't there."""

from pathlib import Path
from unittest.mock import MagicMock

from app.models.media import CodecType
from app.services.ffprobe import FFProbeService, ProbeResult, StreamInfo

STREAM = StreamInfo(stream_index=0, codec_type=CodecType.VIDEO, codec_name="h264")


def _client(requests: list):
    async def stream_media(file_id, offset=0, limit=0):
        requests.append((offset, limit))
        for i in range(offset, offset + limit):
            yield bytes([i % 256]) * 10

    return MagicMock(stream_media=stream_media)


async def test_probes_the_first_4_mb_only(monkeypatch):
    service, requests = FFProbeService(), []

    async def probe(path):
        return ProbeResult(duration_seconds=2728, streams=[STREAM])

    monkeypatch.setattr(service, "probe_file", probe)
    result = await service.analyze_from_telegram(_client(requests), "fid")

    assert result and result.duration_seconds == 2728
    assert requests == [(0, 4)]


async def test_reads_on_up_to_50_mb_when_the_head_is_not_enough(monkeypatch):
    service, requests, seen = FFProbeService(), [], []

    async def probe(path):
        data = Path(path).read_bytes()
        seen.append(len(data))
        if len(data) < 50 * 10:
            return ProbeResult(duration_seconds=None, streams=[STREAM])
        return ProbeResult(duration_seconds=60, streams=[STREAM])

    monkeypatch.setattr(service, "probe_file", probe)
    result = await service.analyze_from_telegram(_client(requests), "fid")

    assert result and result.duration_seconds == 60
    assert requests == [(0, 4), (4, 46)]  # continues where it stopped, no re-download
    assert seen == [40, 500]
