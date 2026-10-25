"""Tests for the subtitle extraction service.

Coverage:
- Pure functions: time formatters, ASS/SRT builders, read-range merger
- EBML binary parsing: parse_tracks, parse_cluster_for_subtitles
- Client acquisition patterns:
    extract_via_scan  → NO batch_mode (documented design trade-off)
    _parallel_fetch_and_parse → uses batch_mode correctly
- Integration: extract_all_subtitles on a synthetic MKV (subtitle Cues read block by
  block, fallback to reading the clusters, image tracks skipped)
- read_small: Telegram's GetFile alignment rules
"""


import pytest

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
from app.services.subtitles.mkv_extractor import extract_all_subtitles

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
        self.read_window_calls: list[tuple[int, int]] = []
        self.batch_mode_entered = 0

    async def read_range(self, start: int, end: int):
        self.read_range_calls.append((start, end))
        chunk = self._data[start : min(end, len(self._data))]
        if chunk:
            yield chunk

    async def read_window(self, start: int, end: int) -> bytes:
        self.read_window_calls.append((start, end))
        return self._data[start:end]

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
        events = parse_cluster_for_subtitles(b"\x00" * 50, 0, {3}, 1_000_000)
        assert events == []

    def test_block_for_wrong_track_skipped(self):
        block = _simple_block(track_num=1, relative_time=0, payload=b"Video")
        data = _cluster(timecode=0, blocks=[block])
        events = parse_cluster_for_subtitles(data, 0, tracks={3}, timecode_scale=1_000_000)
        assert events == []

    def test_block_for_correct_track_extracted(self):
        payload = b"Hello subtitle"
        block = _simple_block(track_num=3, relative_time=100, payload=payload)
        data = _cluster(timecode=1000, blocks=[block])
        events = parse_cluster_for_subtitles(data, 0, tracks={3}, timecode_scale=1_000_000)
        assert len(events) == 1
        assert events[0].data == payload

    def test_timecode_scale_applied(self):
        # cluster_timecode=1000, relative=0, scale=1_000_000
        # → timestamp_ms = int(1000 * 1_000_000 / 1_000_000) = 1000
        block = _simple_block(track_num=3, relative_time=0, payload=b"T")
        data = _cluster(timecode=1000, blocks=[block])
        events = parse_cluster_for_subtitles(data, 0, {3}, 1_000_000)
        assert events[0].timestamp_ms == 1000

    def test_relative_time_added_to_cluster_timecode(self):
        # cluster_timecode=500, relative=300 → raw_ts=800
        # scale=1_000_000 → timestamp_ms=800
        block = _simple_block(track_num=3, relative_time=300, payload=b"X")
        data = _cluster(timecode=500, blocks=[block])
        events = parse_cluster_for_subtitles(data, 0, {3}, 1_000_000)
        assert events[0].timestamp_ms == 800

    def test_multiple_blocks_in_cluster(self):
        blocks = [
            _simple_block(track_num=3, relative_time=0,   payload=b"Line 1"),
            _simple_block(track_num=3, relative_time=500, payload=b"Line 2"),
        ]
        data = _cluster(timecode=0, blocks=blocks)
        events = parse_cluster_for_subtitles(data, 0, {3}, 1_000_000)
        assert len(events) == 2

    def test_empty_cluster_no_events(self):
        data = _cluster(timecode=0, blocks=[])
        events = parse_cluster_for_subtitles(data, 0, {3}, 1_000_000)
        assert events == []

    def test_block_duration_scaled_like_timestamp(self):
        # TimecodeScale 100_000 ns = 0.1 ms per unit: 1000 units → 100 ms, 20000 → 2000 ms
        block = bytes([0x83]) + (0).to_bytes(2, "big") + bytes([0x00]) + b"Hi"
        group = _elem(bytes([0xA0]), _elem(bytes([0xA1]), block) + _elem(bytes([0x9B]), (20000).to_bytes(2, "big")))
        events = parse_cluster_for_subtitles(_cluster(timecode=1000, blocks=[group]), 0, {3}, 100_000)
        assert (events[0].timestamp_ms, events[0].duration_ms) == (100, 2000)


class TestSafeFontFilename:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Arial.ttf", "Arial.ttf"),
            ("../../etc/evil.ttf", "evil.ttf"),
            ("..\\..\\evil.ttf", "evil.ttf"),
            ("/abs/x.otf", "x.otf"),
            ("..", "font_7.ttf"),
            (None, "font_7.ttf"),
        ],
    )
    def test_keeps_only_base_name(self, name, expected):
        from app.services.subtitles.service import safe_font_filename

        assert safe_font_filename(name, 7) == expected


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
        await extract_via_scan(reader, 0, {3}, 1_000_000)
        assert len(reader.read_range_calls) == 1

    async def test_larger_file_multiple_independent_read_calls(self):
        # 21 MB → chunks: [0,10MB), [10MB,20MB), [20MB,21MB) = 3 calls
        reader = MockReader(total_size=21 * 1024 * 1024)
        await extract_via_scan(reader, 0, {3}, 1_000_000)
        assert len(reader.read_range_calls) == 3

    async def test_no_batch_mode_entered(self):
        """extract_via_scan never enters batch_mode — the known design issue."""
        reader = MockReader(total_size=5 * 1024 * 1024)
        await extract_via_scan(reader, 0, {3}, 1_000_000)
        assert reader.batch_mode_entered == 0  # batch_mode is NOT used

    async def test_reads_start_at_header_size(self):
        header_size = 1 * 1024 * 1024
        reader = MockReader(total_size=3 * 1024 * 1024)
        await extract_via_scan(reader, header_size, {3}, 1_000_000)
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
        events = await extract_via_scan(reader, 0, {3}, 1_000_000)
        assert events == []
        assert reader.call_count == 1  # stopped on first failure

    async def test_cluster_across_chunk_boundary_is_complete(self):
        # The first cluster runs past the 10 MB chunk: the line cut in two and the one
        # after the cut must both come out whole
        video = bytes([0x81]) + bytes(3) + bytes(10 * 1024 * 1024 - 200)
        across = b"Across the cut " * 20
        first = (
            _elem(bytes([0xE7]), (1000).to_bytes(2, "big"))
            + b"\xa3" + _size(len(video), 4) + video
            + _simple_block(3, 0, across)
            + _simple_block(3, 50, b"After the cut")
        )
        second = _elem(bytes([0xE7]), (5000).to_bytes(2, "big")) + _simple_block(3, 0, b"Next cluster")
        data = b"".join(b"\x1f\x43\xb6\x75" + _size(len(c), 8) + c for c in (first, second))

        events = await extract_via_scan(MockReader(data), 0, {3}, 1_000_000)

        assert [(e.timestamp_ms, e.data) for e in events] == [
            (1000, across), (1050, b"After the cut"), (5000, b"Next cluster")
        ]

    async def test_cluster_in_data_is_extracted(self):
        block = _simple_block(track_num=3, relative_time=0, payload=b"Subtitle text")
        data = _cluster(timecode=1000, blocks=[block]) + b"\x00" * 100
        reader = MockReader(data=data)
        events = await extract_via_scan(reader, 0, {3}, 1_000_000)
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
        await _parallel_fetch_and_parse(reader, ranges, {3}, 1_000_000)
        assert reader.batch_mode_entered == 1

    async def test_all_ranges_fetched_inside_batch_mode(self):
        reader = MockReader(total_size=10 * 1024 * 1024)
        ranges = [(0, 128 * 1024), (500_000, 500_000 + 128 * 1024)]
        await _parallel_fetch_and_parse(reader, ranges, {3}, 1_000_000)
        fetched_starts = {s for s, _ in reader.read_range_calls}
        assert 0 in fetched_starts
        assert 500_000 in fetched_starts

    async def test_empty_ranges_returns_empty_events(self):
        reader = MockReader(total_size=10 * 1024 * 1024)
        events = await _parallel_fetch_and_parse(reader, [], {3}, 1_000_000)
        assert events == []
        assert len(reader.read_range_calls) == 0

    async def test_ranges_beyond_total_size_skipped(self):
        # total_size=100 → ranges at 1000+ are filtered before fetching
        reader = MockReader(total_size=100)
        await _parallel_fetch_and_parse(reader, [(1000, 2000), (2000, 3000)], {3}, 1_000_000)
        assert len(reader.read_range_calls) == 0

    async def test_batch_mode_entered_even_with_no_valid_ranges(self):
        # The async with block is always entered even when no tasks are created
        reader = MockReader(total_size=10 * 1024 * 1024)
        await _parallel_fetch_and_parse(reader, [], {3}, 1_000_000)
        assert reader.batch_mode_entered == 1


# ─────────────────────────────────────────────────────────────────────────────
# Integration: extract_all_subtitles on a synthetic MKV
# ─────────────────────────────────────────────────────────────────────────────

LINES = [(1000, 2000, b"First line"), (61000, 1500, b"Second line"), (125000, 3000, b"Third line")]


def _size(n: int, length: int) -> bytes:
    """EBML size VINT of a fixed length (muxers often write Cluster sizes on 8 bytes)."""
    return ((1 << (7 * length)) | n).to_bytes(length, "big")


def _mkv(subtitle_cues: bool = True, cluster_size_len: int = 8) -> bytes:
    """Video track 1, text subtitle track 3, PGS track 4; one cluster per line in LINES, the
    subtitle BlockGroup between two video blocks; Cues for the video, and for the subtitles
    (with relative position and duration, like mkvmerge) unless subtitle_cues=False.
    TimecodeScale is 500 µs: 2 units per ms. Over 3 MB, so the cluster-Cues fallback runs.
    """
    info = _elem(b"\x15\x49\xa9\x66", _elem(b"\x2a\xd7\xb1", (500_000).to_bytes(4, "big")))
    tracks = _tracks_block([
        _track_entry(1, 1, "V_MPEG4/ISO/AVC"),
        _track_entry(3, 17, "S_TEXT/UTF8"),
        _track_entry(4, 17, "S_HDMV/PGS"),
    ])

    def seek_head(cues_position: int) -> bytes:
        seek = _elem(b"\x53\xab", b"\x1c\x53\xbb\x6b") + _elem(b"\x53\xac", cues_position.to_bytes(8, "big"))
        return _elem(b"\x11\x4d\x9b\x74", _elem(b"\x4d\xbb", seek))

    position = len(seek_head(0)) + len(info) + len(tracks)
    clusters, points = [], b""
    for i, (start_ms, duration_ms, text) in enumerate(LINES):
        cluster_time = start_ms * 2 - 100
        video = b"\x00" * 1_100_000
        if i == 1:
            # Bytes that parse as a 4-byte SimpleBlock of track 3 right before the subtitle:
            # a wrong start the vote must reject
            video += b"\xa3\x84\x83\x00\x00"
        before = _elem(b"\xe7", cluster_time.to_bytes(4, "big")) + _simple_block(1, 0, video)
        block = bytes([0x83]) + (100).to_bytes(2, "big") + b"\x00" + text
        group = _elem(b"\xa0", _elem(b"\xa1", block) + _elem(b"\x9b", (duration_ms * 2).to_bytes(2, "big")))
        content = before + group + _simple_block(1, 10, b"\x00" * 1000)
        clusters.append(b"\x1f\x43\xb6\x75" + _size(len(content), cluster_size_len) + content)

        cluster_pos = _elem(b"\xf1", position.to_bytes(4, "big"))
        points += _elem(b"\xbb", _elem(b"\xb3", cluster_time.to_bytes(4, "big"))
                        + _elem(b"\xb7", _elem(b"\xf7", b"\x01") + cluster_pos))
        if subtitle_cues:
            points += _elem(b"\xbb", _elem(b"\xb3", (start_ms * 2).to_bytes(4, "big")) + _elem(
                b"\xb7",
                _elem(b"\xf7", b"\x03") + cluster_pos
                + _elem(b"\xf0", len(before).to_bytes(4, "big"))
                + _elem(b"\xb2", (duration_ms * 2).to_bytes(4, "big")),
            ))
        position += len(clusters[-1])

    cues = b"\x1c\x53\xbb\x6b" + _size(len(points), 4) + points
    body = seek_head(position) + info + tracks + b"".join(clusters) + cues
    return b"\x1a\x45\xdf\xa3\x80" + b"\x18\x53\x80\x67" + _size(len(body), 8) + body


def _lines(events: list[SubtitleEvent] | None) -> list[tuple[int, int | None, bytes]]:
    assert events is not None
    return [(e.timestamp_ms, e.duration_ms, e.data) for e in events]


class TestExtractAllSubtitles:
    @pytest.mark.parametrize("cluster_size_len", [8, 4])
    async def test_reads_only_the_cued_blocks(self, cluster_size_len):
        reader = MockReader(_mkv(cluster_size_len=cluster_size_len))
        result = await extract_all_subtitles(reader)
        assert result is not None

        assert [t.track_number for t, _ in result] == [3, 4]
        assert _lines(result[0][1]) == LINES
        assert result[1][1] is None  # PGS: not extracted
        assert reader.read_range_calls == [(0, 1024 * 1024)]  # the header, nothing else
        assert sum(end - start for start, end in reader.read_window_calls) < 64 * 1024
        assert reader.batch_mode_entered == 1

    async def test_without_subtitle_cues_reads_the_clusters(self):
        reader = MockReader(_mkv(subtitle_cues=False))
        result = await extract_all_subtitles(reader)
        assert result is not None

        assert _lines(result[0][1]) == LINES
        assert result[1][1] is None
        assert sum(end - start for start, end in reader.read_range_calls) > 3 * 1024 * 1024

    async def test_background_run_skips_tracks_needing_a_full_read(self):
        reader = MockReader(_mkv(subtitle_cues=False))
        result = await extract_all_subtitles(reader, full_read=False)

        assert result is not None
        assert [events for _, events in result] == [None, None]  # no cues: left for a request
        assert reader.read_range_calls == [(0, 1024 * 1024)]  # the header, nothing else

    async def test_header_read_failure_returns_none(self):
        class FailReader(MockReader):
            async def read_range(self, start, end):
                raise Exception("Network error")
                yield

        assert await extract_all_subtitles(FailReader(total_size=100 * 1024 * 1024)) is None

    async def test_no_subtitle_tracks(self):
        assert await extract_all_subtitles(MockReader(b"\x00" * 500)) == []


class TestCacheAllSubtitleTracks:
    async def test_writes_ass_and_srt_per_text_track(self, tmp_path, monkeypatch):
        from app.services.subtitles import cache

        monkeypatch.setattr(cache, "SUBTITLE_CACHE_DIR", tmp_path)
        cached = await cache.cache_all_subtitle_tracks(MockReader(_mkv()), 7, [2, 5])

        assert cached == 1
        assert b"First line" in (tmp_path / "7_2.ass").read_bytes()
        assert b"00:01:01,000 --> 00:01:02,500" in (tmp_path / "7_2.srt").read_bytes()
        assert not (tmp_path / "7_5.ass").exists()  # the PGS track


class TestVideoKeyframes:
    """Seek keyframes come from the Cues of the video track only: mkvmerge also indexes
    every subtitle block, and a seek snapped to one starts the copied video mid-GOP."""

    def test_only_the_video_tracks_cue_points(self):
        from app.services.mkv_cues import parse_cues, video_track_number

        data = _mkv()
        cues = data.rfind(b"\x1c\x53\xbb\x6b")  # the Cues element, past the SeekHead's entry
        video = [(start * 2 - 100) * 0.0005 for start, _, _ in LINES]  # cluster times

        assert parse_cues(data, cues, 500_000, video_track_number(data)) == pytest.approx(video)
        assert len(parse_cues(data, cues, 500_000)) == 2 * len(LINES)  # subtitle cues too

    def test_video_track_found_past_the_seek_head_entry(self):
        from app.services.mkv_cues import video_track_number

        seek = _elem(b"\x53\xab", b"\x16\x54\xae\x6b") + _elem(b"\x53\xac", (64).to_bytes(8, "big"))
        header = _elem(b"\x11\x4d\x9b\x74", _elem(b"\x4d\xbb", seek)) + _tracks_block(
            [_track_entry(1, 17, "S_TEXT/UTF8"), _track_entry(2, 1, "V_MPEGH/ISO/HEVC")]
        )

        assert video_track_number(header) == 2


# ─────────────────────────────────────────────────────────────────────────────
# read_small: Telegram GetFile rules
# ─────────────────────────────────────────────────────────────────────────────


class TestReadSmall:
    def _client(self, data: bytes, requests: list):
        from unittest.mock import MagicMock

        from pyrogram import raw

        class Session:
            is_connected = MagicMock(is_set=MagicMock(return_value=True))

            async def send(self, query, wait_response=True, timeout=None):
                o, n = query.offset, query.limit
                assert o % 4096 == 0 and n % 4096 == 0 and (1 << 20) % n == 0
                assert o >> 20 == (o + n - 1) >> 20  # never across a 1 MB boundary
                requests.append((o, n))
                return raw.types.upload.File(
                    type=raw.types.storage.FileUnknown(), mtime=0, bytes=data[o : o + n]
                )

        return MagicMock(media_sessions={4: Session()}, sleep_threshold=10)

    def _file_id(self) -> str:
        from pyrogram.file_id import FileId, FileType

        return FileId(
            file_type=FileType.DOCUMENT, dc_id=4, media_id=1, access_hash=2, file_reference=b"r"
        ).encode()

    @pytest.mark.parametrize(
        ("offset", "length"),
        [(0, 10), (5000, 3000), (4095, 2), ((1 << 20) - 100, 300), (2_000_000, 70_000)],
    )
    async def test_returns_exact_bytes_with_valid_requests(self, offset, length):
        from app.services.streaming.download import read_small

        data = bytes(range(256)) * 12_000  # ~3 MB
        requests = []
        result = await read_small(self._client(data, requests), self._file_id(), offset, length)

        assert result == data[offset : offset + length]
        assert sum(n for _, n in requests) <= max(4 * length, 8192)

    async def test_no_media_session_returns_none(self):
        from unittest.mock import MagicMock

        from app.services.streaming.download import read_small

        assert await read_small(MagicMock(media_sessions={}), self._file_id(), 0, 10) is None
