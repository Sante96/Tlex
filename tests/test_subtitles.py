"""Tests for the subtitle extraction service.

Coverage:
- Pure functions: time formatters, ASS/SRT builders, read-range merger
- EBML binary parsing: parse_tracks, parse_cluster_for_subtitles
- Client acquisition patterns:
    extract_via_scan  → NO batch_mode (documented design trade-off)
    _parallel_fetch_and_parse → uses batch_mode correctly
- Integration: extract_subtitle_direct orchestrator (header read, track
  selection, format output, fallback to scan when cues missing)
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.subtitles.builders import (
    _format_ass_time,
    _format_srt_time,
    build_ass_content,
    build_srt_content,
)
from app.services.subtitles.cluster_reader import (
    _build_read_ranges,
    _parallel_fetch_and_parse,
    extract_via_scan,
)
from app.services.subtitles.ebml_parser import (
    MkvSubtitleTrack,
    SubtitleEvent,
    parse_cluster_for_subtitles,
    parse_tracks,
)
from app.services.subtitles.mkv_extractor import extract_subtitle_direct


# ─────────────────────────────────────────────────────────────────────────────
# EBML construction helpers
# ─────────────────────────────────────────────────────────────────────────────


def _vint(n: int) -> bytes:
    """Encode n as an EBML variable-length integer (used for element sizes)."""
    if n <= 126:
        return bytes([0x80 | n])
    elif n <= 16382:
        return bytes([0x40 | (n >> 8), n & 0xFF])
    else:
        return bytes([0x20 | (n >> 16), (n >> 8) & 0xFF, n & 0xFF])


def _elem(id_bytes: bytes, data: bytes) -> bytes:
    """Wrap data in an EBML element: ID bytes + size VINT + data."""
    return id_bytes + _vint(len(data)) + data


def _track_entry(
    track_number: int,
    track_type: int,
    codec_id: str,
    codec_private: bytes | None = None,
) -> bytes:
    """Build a TrackEntry EBML element."""
    content = (
        _elem(bytes([0xD7]), bytes([track_number]))  # TrackNumber
        + _elem(bytes([0x83]), bytes([track_type]))  # TrackType
        + _elem(bytes([0x86]), codec_id.encode())     # CodecID
    )
    if codec_private is not None:
        content += _elem(bytes([0x63, 0xA2]), codec_private)  # CodecPrivate
    return _elem(bytes([0xAE]), content)


def _tracks_block(entries: list[bytes]) -> bytes:
    """Build a Tracks EBML element (ID 0x1654AE6B) containing entries."""
    content = b"".join(entries)
    return bytes([0x16, 0x54, 0xAE, 0x6B]) + _vint(len(content)) + content


def _simple_block(track_num: int, relative_time: int, payload: bytes) -> bytes:
    """Build a SimpleBlock EBML element (ID 0xA3)."""
    block_data = (
        bytes([0x80 | track_num])          # track VINT (1-byte for track ≤ 63)
        + relative_time.to_bytes(2, "big") # signed int16 relative timecode
        + bytes([0x00])                    # flags
        + payload
    )
    return _elem(bytes([0xA3]), block_data)


def _cluster(timecode: int, blocks: list[bytes]) -> bytes:
    """Build a Cluster EBML element (ID 0x1F43B675)."""
    tc_elem = _elem(bytes([0xE7]), timecode.to_bytes(2, "big"))
    content = tc_elem + b"".join(blocks)
    return bytes([0x1F, 0x43, 0xB6, 0x75]) + _vint(len(content)) + content


# ─────────────────────────────────────────────────────────────────────────────
# Minimal mock VirtualStreamReader
# ─────────────────────────────────────────────────────────────────────────────


class MockReader:
    """Lightweight mock of VirtualStreamReader for subtitle tests.

    Serves in-memory bytes; tracks read_range calls and batch_mode entries.
    Setting total_size > len(data) simulates a large sparse file without
    allocating memory.
    """

    def __init__(self, data: bytes = b"", total_size: int | None = None):
        self._data = data
        self.total_size = total_size if total_size is not None else len(data)
        self.read_range_calls: list[tuple[int, int]] = []
        self.batch_mode_entered = 0

    async def read_range(self, start: int, end: int):
        self.read_range_calls.append((start, end))
        chunk = self._data[start : min(end, len(self._data))]
        if chunk:
            yield chunk

    class _BatchCtx:
        def __init__(self, outer: "MockReader"):
            self._outer = outer

        async def __aenter__(self):
            self._outer.batch_mode_entered += 1
            return self

        async def __aexit__(self, *args):
            pass

    def batch_mode(self):
        return self._BatchCtx(self)


# ─────────────────────────────────────────────────────────────────────────────
# Time formatters
# ─────────────────────────────────────────────────────────────────────────────


class TestFormatAssTime:
    def test_zero(self):
        assert _format_ass_time(0) == "0:00:00.00"

    def test_centiseconds(self):
        assert _format_ass_time(1500) == "0:00:01.50"

    def test_one_minute(self):
        assert _format_ass_time(61000) == "0:01:01.00"

    def test_one_hour(self):
        assert _format_ass_time(3661000) == "1:01:01.00"

    def test_fractional_centiseconds(self):
        # 999 ms → floor(999/10) = 99 centiseconds
        assert _format_ass_time(999) == "0:00:00.99"

    def test_exactly_one_hour(self):
        assert _format_ass_time(3600000) == "1:00:00.00"


class TestFormatSrtTime:
    def test_zero(self):
        assert _format_srt_time(0) == "00:00:00,000"

    def test_milliseconds(self):
        assert _format_srt_time(1500) == "00:00:01,500"

    def test_one_minute(self):
        assert _format_srt_time(61000) == "00:01:01,000"

    def test_one_hour(self):
        assert _format_srt_time(3661500) == "01:01:01,500"

    def test_zero_padding(self):
        assert _format_srt_time(1001) == "00:00:01,001"


# ─────────────────────────────────────────────────────────────────────────────
# SRT builder
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildSrtContent:
    def _ev(self, ts: int, dur: int, text: str) -> SubtitleEvent:
        return SubtitleEvent(timestamp_ms=ts, duration_ms=dur, data=text.encode())

    def test_single_event(self):
        result = build_srt_content([self._ev(1000, 2000, "Hello")]).decode()
        assert "1\n" in result
        assert "00:00:01,000 --> 00:00:03,000" in result
        assert "Hello" in result

    def test_events_sorted_by_timestamp(self):
        events = [self._ev(5000, 1000, "Second"), self._ev(1000, 1000, "First")]
        result = build_srt_content(events).decode()
        assert result.index("First") < result.index("Second")

    def test_default_duration_5000ms_when_none(self):
        events = [SubtitleEvent(timestamp_ms=0, duration_ms=None, data=b"No dur")]
        result = build_srt_content(events).decode()
        assert "00:00:00,000 --> 00:00:05,000" in result

    def test_sequential_numbering(self):
        events = [self._ev(i * 1000, 500, f"Line {i}") for i in range(3)]
        result = build_srt_content(events).decode()
        for n in ("1\n", "2\n", "3\n"):
            assert n in result

    def test_empty_returns_empty_bytes(self):
        assert build_srt_content([]) == b""

    def test_returns_bytes(self):
        assert isinstance(build_srt_content([self._ev(0, 1000, "x")]), bytes)


# ─────────────────────────────────────────────────────────────────────────────
# ASS builder
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildAssContent:
    def _srt_track(self) -> MkvSubtitleTrack:
        return MkvSubtitleTrack(track_number=1, codec_id="S_TEXT/UTF8", codec_private=None)

    def _ev(self, ts: int, text: str) -> SubtitleEvent:
        return SubtitleEvent(timestamp_ms=ts, duration_ms=1000, data=text.encode())

    def test_minimal_header_generated_without_codec_private(self):
        result = build_ass_content(self._srt_track(), [self._ev(0, "Hi")]).decode()
        assert "[Script Info]" in result
        assert "[Events]" in result
        assert "Dialogue:" in result

    def test_dialogue_contains_text(self):
        result = build_ass_content(self._srt_track(), [self._ev(0, "Hello ASS")]).decode()
        assert "Hello ASS" in result

    def test_events_sorted_by_timestamp(self):
        events = [self._ev(5000, "Late"), self._ev(0, "Early")]
        result = build_ass_content(self._srt_track(), events).decode()
        assert result.index("Early") < result.index("Late")

    def test_with_codec_private_header(self):
        header = (
            b"[Script Info]\nScriptType: v4.00+\n\n"
            b"[Events]\nFormat: Layer, Start, End, Style, Name, "
            b"MarginL, MarginR, MarginV, Effect, Text\n"
        )
        track = MkvSubtitleTrack(track_number=1, codec_id="S_TEXT/ASS", codec_private=header)
        result = build_ass_content(track, [self._ev(0, "0,0,Default,,0,0,0,,Hello")]).decode()
        assert "[Script Info]" in result
        assert "Dialogue:" in result

    def test_empty_events_still_has_header(self):
        result = build_ass_content(self._srt_track(), []).decode()
        assert "[Script Info]" in result

    def test_returns_bytes(self):
        assert isinstance(build_ass_content(self._srt_track(), []), bytes)


# ─────────────────────────────────────────────────────────────────────────────
# Read-range merger
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildReadRanges:
    def test_empty_input_returns_empty(self):
        assert _build_read_ranges([]) == []

    def test_single_position(self):
        result = _build_read_ranges([1_000_000])
        assert len(result) == 1
        start, end = result[0]
        assert start == 1_000_000
        assert end == 1_000_000 + 128 * 1024  # cluster_read_size = 128 KB

    def test_two_close_positions_merged(self):
        # 1 MB gap < 10 MB limit → merged into one range
        result = _build_read_ranges([0, 1_000_000])
        assert len(result) == 1

    def test_two_far_positions_stay_separate(self):
        # 11 MB gap > 10 MB limit → two separate ranges
        result = _build_read_ranges([0, 11 * 1024 * 1024])
        assert len(result) == 2

    def test_exceeds_max_merged_size_forces_split(self):
        # 32 positions × 1 MiB apart → span exceeds the 30 MiB merge cap → split
        positions = [i * 1_048_576 for i in range(32)]
        result = _build_read_ranges(positions)
        assert len(result) >= 2

    def test_result_is_list_of_2tuples(self):
        result = _build_read_ranges([100, 200])
        assert isinstance(result, list)
        assert isinstance(result[0], tuple)
        assert len(result[0]) == 2

    def test_output_ranges_are_ordered(self):
        positions = sorted([5_000_000, 1_000_000, 3_000_000])
        result = _build_read_ranges(positions)
        starts = [r[0] for r in result]
        assert starts == sorted(starts)


# ─────────────────────────────────────────────────────────────────────────────
# EBML: parse_tracks
# ─────────────────────────────────────────────────────────────────────────────


class TestParseTracks:
    def test_empty_data_returns_empty(self):
        assert parse_tracks(b"") == []

    def test_all_zeros_returns_empty(self):
        assert parse_tracks(b"\x00" * 200) == []

    def test_single_subtitle_track(self):
        data = _tracks_block([_track_entry(3, 17, "S_TEXT/UTF8")])
        tracks = parse_tracks(data)
        assert len(tracks) == 1
        assert tracks[0].track_number == 3
        assert tracks[0].codec_id == "S_TEXT/UTF8"
        assert tracks[0].codec_private is None

    def test_video_track_not_returned(self):
        # TrackType=1 = video → filtered out
        data = _tracks_block([_track_entry(1, 1, "V_MPEG4/ISO/AVC")])
        assert parse_tracks(data) == []

    def test_audio_track_not_returned(self):
        # TrackType=2 = audio
        data = _tracks_block([_track_entry(2, 2, "A_AAC")])
        assert parse_tracks(data) == []

    def test_multiple_subtitle_tracks(self):
        data = _tracks_block([
            _track_entry(3, 17, "S_TEXT/ASS"),
            _track_entry(4, 17, "S_TEXT/UTF8"),
        ])
        tracks = parse_tracks(data)
        assert len(tracks) == 2
        assert {t.codec_id for t in tracks} == {"S_TEXT/ASS", "S_TEXT/UTF8"}

    def test_codec_private_preserved(self):
        private = b"[Script Info]\nSomeData\n"
        data = _tracks_block([_track_entry(3, 17, "S_TEXT/ASS", codec_private=private)])
        tracks = parse_tracks(data)
        assert len(tracks) == 1
        assert tracks[0].codec_private == private

    def test_tracks_element_embedded_in_surrounding_junk(self):
        entry = _track_entry(5, 17, "S_TEXT/UTF8")
        header = _tracks_block([entry])
        data = b"\x00" * 50 + header + b"\xFF" * 50
        tracks = parse_tracks(data)
        assert len(tracks) == 1
        assert tracks[0].track_number == 5


# ─────────────────────────────────────────────────────────────────────────────
# EBML: parse_cluster_for_subtitles
# ─────────────────────────────────────────────────────────────────────────────


class TestParseCluster:
    def test_wrong_id_returns_empty(self):
        events = parse_cluster_for_subtitles(b"\x00" * 50, 0, 3, 1_000_000)
        assert events == []

    def test_block_for_wrong_track_skipped(self):
        block = _simple_block(track_num=1, relative_time=0, payload=b"Video")
        data = _cluster(timecode=0, blocks=[block])
        events = parse_cluster_for_subtitles(data, 0, target_track=3, timecode_scale=1_000_000)
        assert events == []

    def test_block_for_correct_track_extracted(self):
        payload = b"Hello subtitle"
        block = _simple_block(track_num=3, relative_time=100, payload=payload)
        data = _cluster(timecode=1000, blocks=[block])
        events = parse_cluster_for_subtitles(data, 0, target_track=3, timecode_scale=1_000_000)
        assert len(events) == 1
        assert events[0].data == payload

    def test_timecode_scale_applied(self):
        # cluster_timecode=1000, relative=0, scale=1_000_000
        # → timestamp_ms = int(1000 * 1_000_000 / 1_000_000) = 1000
        block = _simple_block(track_num=3, relative_time=0, payload=b"T")
        data = _cluster(timecode=1000, blocks=[block])
        events = parse_cluster_for_subtitles(data, 0, 3, 1_000_000)
        assert events[0].timestamp_ms == 1000

    def test_relative_time_added_to_cluster_timecode(self):
        # cluster_timecode=500, relative=300 → raw_ts=800
        # scale=1_000_000 → timestamp_ms=800
        block = _simple_block(track_num=3, relative_time=300, payload=b"X")
        data = _cluster(timecode=500, blocks=[block])
        events = parse_cluster_for_subtitles(data, 0, 3, 1_000_000)
        assert events[0].timestamp_ms == 800

    def test_multiple_blocks_in_cluster(self):
        blocks = [
            _simple_block(track_num=3, relative_time=0,   payload=b"Line 1"),
            _simple_block(track_num=3, relative_time=500, payload=b"Line 2"),
        ]
        data = _cluster(timecode=0, blocks=blocks)
        events = parse_cluster_for_subtitles(data, 0, 3, 1_000_000)
        assert len(events) == 2

    def test_empty_cluster_no_events(self):
        data = _cluster(timecode=0, blocks=[])
        events = parse_cluster_for_subtitles(data, 0, 3, 1_000_000)
        assert events == []


# ─────────────────────────────────────────────────────────────────────────────
# Client acquisition: extract_via_scan  (KNOWN DESIGN ISSUE: no batch_mode)
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractViaScanClientHandling:
    """Document and verify client acquisition behavior of extract_via_scan.

    KNOWN DESIGN ISSUE: extract_via_scan does NOT use batch_mode.
    Each 10 MB chunk triggers an independent read_range call, meaning each
    chunk acquires and releases Pyrogram clients separately.  On a stressed
    pool this can cause intermittent chunk-level failures even when the pool
    has capacity overall.

    The ideal fix is to wrap the entire function in ``async with reader.batch_mode()``.
    These tests document the *current* behaviour so any future change is visible.
    """

    async def test_small_file_one_read_call(self):
        reader = MockReader(total_size=1 * 1024 * 1024)
        await extract_via_scan(reader, 0, 3, 1_000_000)
        assert len(reader.read_range_calls) == 1

    async def test_larger_file_multiple_independent_read_calls(self):
        # 21 MB → chunks: [0,10MB), [10MB,20MB), [20MB,21MB) = 3 calls
        reader = MockReader(total_size=21 * 1024 * 1024)
        await extract_via_scan(reader, 0, 3, 1_000_000)
        assert len(reader.read_range_calls) == 3

    async def test_no_batch_mode_entered(self):
        """extract_via_scan never enters batch_mode — the known design issue."""
        reader = MockReader(total_size=5 * 1024 * 1024)
        await extract_via_scan(reader, 0, 3, 1_000_000)
        assert reader.batch_mode_entered == 0  # batch_mode is NOT used

    async def test_reads_start_at_header_size(self):
        header_size = 1 * 1024 * 1024
        reader = MockReader(total_size=3 * 1024 * 1024)
        await extract_via_scan(reader, header_size, 3, 1_000_000)
        assert all(start >= header_size for start, _ in reader.read_range_calls)

    async def test_read_error_stops_scan_and_returns_partial(self):
        """A read failure breaks the loop; earlier results are still returned."""
        class ErrorOnFirstRead:
            total_size = 10 * 1024 * 1024
            batch_mode_entered = 0
            call_count = 0

            async def read_range(self, start, end):
                self.call_count += 1
                raise Exception("Simulated failure")
                yield  # make this an async generator

            def batch_mode(self):
                raise AssertionError("batch_mode must not be called")

        reader = ErrorOnFirstRead()
        events = await extract_via_scan(reader, 0, 3, 1_000_000)
        assert events == []
        assert reader.call_count == 1  # stopped on first failure

    async def test_cluster_in_data_is_extracted(self):
        block = _simple_block(track_num=3, relative_time=0, payload=b"Subtitle text")
        data = _cluster(timecode=1000, blocks=[block]) + b"\x00" * 100
        reader = MockReader(data=data)
        events = await extract_via_scan(reader, 0, 3, 1_000_000)
        assert len(events) == 1
        assert events[0].data == b"Subtitle text"


# ─────────────────────────────────────────────────────────────────────────────
# Client acquisition: _parallel_fetch_and_parse  (correctly uses batch_mode)
# ─────────────────────────────────────────────────────────────────────────────


class TestParallelFetchBatchMode:
    """Verify that parallel cluster fetching uses batch_mode correctly.

    _parallel_fetch_and_parse wraps ALL parallel reads inside a single
    ``async with reader.batch_mode()`` block.  This means one client
    acquisition cycle regardless of how many cluster ranges are fetched.
    """

    async def test_batch_mode_entered_exactly_once(self):
        reader = MockReader(total_size=10 * 1024 * 1024)
        ranges = [(0, 128 * 1024), (1_000_000, 1_000_000 + 128 * 1024)]
        await _parallel_fetch_and_parse(reader, ranges, 3, 1_000_000)
        assert reader.batch_mode_entered == 1

    async def test_all_ranges_fetched_inside_batch_mode(self):
        reader = MockReader(total_size=10 * 1024 * 1024)
        ranges = [(0, 128 * 1024), (500_000, 500_000 + 128 * 1024)]
        await _parallel_fetch_and_parse(reader, ranges, 3, 1_000_000)
        fetched_starts = {s for s, _ in reader.read_range_calls}
        assert 0 in fetched_starts
        assert 500_000 in fetched_starts

    async def test_empty_ranges_returns_empty_events(self):
        reader = MockReader(total_size=10 * 1024 * 1024)
        events = await _parallel_fetch_and_parse(reader, [], 3, 1_000_000)
        assert events == []
        assert len(reader.read_range_calls) == 0

    async def test_ranges_beyond_total_size_skipped(self):
        # total_size=100 → ranges at 1000+ are filtered before fetching
        reader = MockReader(total_size=100)
        await _parallel_fetch_and_parse(reader, [(1000, 2000), (2000, 3000)], 3, 1_000_000)
        assert len(reader.read_range_calls) == 0

    async def test_batch_mode_entered_even_with_no_valid_ranges(self):
        # The async with block is always entered even when no tasks are created
        reader = MockReader(total_size=10 * 1024 * 1024)
        await _parallel_fetch_and_parse(reader, [], 3, 1_000_000)
        assert reader.batch_mode_entered == 1


# ─────────────────────────────────────────────────────────────────────────────
# Integration: extract_subtitle_direct
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractSubtitleDirect:
    """End-to-end tests with a MockReader and patched cluster extraction."""

    def _events(self) -> list[SubtitleEvent]:
        return [
            SubtitleEvent(timestamp_ms=1000, duration_ms=2000, data=b"Line 1"),
            SubtitleEvent(timestamp_ms=3000, duration_ms=2000, data=b"Line 2"),
        ]

    def _header_with_track(self, codec_id: str = "S_TEXT/UTF8") -> bytes:
        """Minimal MKV header bytes containing one subtitle track."""
        return _tracks_block([_track_entry(3, 17, codec_id)])

    async def test_header_read_failure_returns_none(self):
        class FailReader:
            total_size = 100 * 1024 * 1024

            async def read_range(self, start, end):
                raise Exception("Network error")
                yield

            def batch_mode(self):
                pass  # not reached

        result = await extract_subtitle_direct(FailReader(), 0, "ass")
        assert result is None

    async def test_no_subtitle_tracks_found_returns_none(self):
        # Data has no Tracks element → parse_tracks returns []
        reader = MockReader(data=b"\x00" * 500)
        result = await extract_subtitle_direct(reader, 0, "ass")
        assert result is None

    async def test_track_index_out_of_range_returns_none(self):
        reader = MockReader(data=self._header_with_track())
        with patch("app.services.subtitles.mkv_extractor.extract_via_cues",
                   new=AsyncMock(return_value=([], False))):
            with patch("app.services.subtitles.mkv_extractor.extract_via_scan",
                       new=AsyncMock(return_value=[])):
                result = await extract_subtitle_direct(reader, 5, "ass")  # only 1 track
        assert result is None

    async def test_returns_srt_bytes_for_srt_format(self):
        reader = MockReader(data=self._header_with_track())
        events = self._events()
        with patch("app.services.subtitles.mkv_extractor.extract_via_cues",
                   new=AsyncMock(return_value=(events, True))):
            result = await extract_subtitle_direct(reader, 0, "srt")
        assert result is not None
        decoded = result.decode()
        assert "00:00:01,000 --> 00:00:03,000" in decoded
        assert "Line 1" in decoded

    async def test_returns_ass_bytes_for_ass_format(self):
        reader = MockReader(data=self._header_with_track("S_TEXT/ASS"))
        events = self._events()
        with patch("app.services.subtitles.mkv_extractor.extract_via_cues",
                   new=AsyncMock(return_value=(events, True))):
            result = await extract_subtitle_direct(reader, 0, "ass")
        assert result is not None
        decoded = result.decode()
        assert "[Script Info]" in decoded
        assert "Dialogue:" in decoded

    async def test_scan_fallback_when_cues_not_found(self):
        reader = MockReader(data=self._header_with_track())
        events = self._events()
        with patch("app.services.subtitles.mkv_extractor.extract_via_cues",
                   new=AsyncMock(return_value=([], False))):
            with patch("app.services.subtitles.mkv_extractor.extract_via_scan",
                       new=AsyncMock(return_value=events)):
                result = await extract_subtitle_direct(reader, 0, "srt")
        assert result is not None
        assert b"Line 1" in result

    async def test_no_events_returns_none(self):
        reader = MockReader(data=self._header_with_track())
        with patch("app.services.subtitles.mkv_extractor.extract_via_cues",
                   new=AsyncMock(return_value=([], False))):
            with patch("app.services.subtitles.mkv_extractor.extract_via_scan",
                       new=AsyncMock(return_value=[])):
                result = await extract_subtitle_direct(reader, 0, "ass")
        assert result is None

    async def test_first_track_selected_by_default(self):
        # Two subtitle tracks — index 0 should select track_number=3
        data = _tracks_block([
            _track_entry(3, 17, "S_TEXT/UTF8"),
            _track_entry(4, 17, "S_TEXT/ASS"),
        ])
        reader = MockReader(data=data)
        events = self._events()
        with patch("app.services.subtitles.mkv_extractor.extract_via_cues",
                   new=AsyncMock(return_value=(events, True))):
            result = await extract_subtitle_direct(reader, 0, "srt")
        assert result is not None  # succeeds for track at index 0

    async def test_second_track_selected_by_index(self):
        data = _tracks_block([
            _track_entry(3, 17, "S_TEXT/UTF8"),
            _track_entry(4, 17, "S_TEXT/ASS"),
        ])
        reader = MockReader(data=data)
        events = self._events()
        with patch("app.services.subtitles.mkv_extractor.extract_via_cues",
                   new=AsyncMock(return_value=(events, True))):
            result = await extract_subtitle_direct(reader, 1, "ass")
        assert result is not None
