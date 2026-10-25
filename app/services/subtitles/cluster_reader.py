"""Cluster reading strategies for MKV subtitle extraction.

Strategies, fastest first:
1. Subtitle Cues: muxers like mkvmerge index every subtitle block (cluster, position
   inside it, time, duration). Read only those blocks: a few KB per line instead of the
   file.
2. Cluster Cues: use the (video) Cues to find clusters and read them all, in parallel.
3. Sequential scan: Fallback when Cues are not available.
2 and 3 read close to the whole file, so they extract every wanted track in that one pass.
"""

import asyncio
from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass

from loguru import logger

from app.services.mkv_cues import (
    CUE_POINT_ID,
    CUE_TIME_ID,
    CUE_TRACK_ID,
    CUE_TRACK_POSITIONS_ID,
    CUES_ID,
    children,
    find_cues_offset,
    parse_cues_for_clusters,
    read_element_id,
    read_uint,
    read_vint,
)
from app.services.subtitles.ebml_parser import (
    BLOCK_GROUP_ID,
    SIMPLE_BLOCK_ID,
    SubtitleEvent,
    parse_block,
    parse_block_group,
    parse_cluster_for_subtitles,
)

CLUSTER_SIGNATURE = bytes([0x1F, 0x43, 0xB6, 0x75])

SEEK_HEAD_ID = 0x114D9B74
SEEK_ID = 0x4DBB
SEEK_ID_ID = 0x53AB
SEEK_POSITION_ID = 0x53AC
CUE_CLUSTER_POSITION_ID = 0xF1
CUE_RELATIVE_POSITION_ID = 0xF0
CUE_DURATION_ID = 0xB2

BLOCK_WINDOW = 4096  # bytes read past a subtitle block's start; longer blocks are re-read
MAX_BLOCK = 1024 * 1024
MERGE_GAP = 4096  # windows closer than this are fetched in one request
MAX_MERGED = 64 * 1024
CONCURRENT_READS = 16


@dataclass
class SubtitleCue:
    """One subtitle block as indexed by Cues (positions relative to the Segment data)."""

    time: int  # absolute timestamp, in TimecodeScale units
    cluster_position: int
    relative_position: int  # from the start of the Cluster's data
    duration: int | None


def find_cues_position(header: bytes, segment_data_start: int) -> int | None:
    """Cues position (relative to the Segment data) from the SeekHead, if the header has it."""
    for elem_id, offset, size in children(header, segment_data_start, len(header)):
        if elem_id != SEEK_HEAD_ID:
            continue
        for seek_id, seek_off, seek_size in children(header, offset, offset + size):
            if seek_id != SEEK_ID:
                continue
            fields = {i: (o, s) for i, o, s in children(header, seek_off, seek_off + seek_size)}
            if SEEK_ID_ID in fields and SEEK_POSITION_ID in fields:
                target = int.from_bytes(
                    header[fields[SEEK_ID_ID][0] : sum(fields[SEEK_ID_ID])], "big"
                )
                if target == CUES_ID:
                    return read_uint(header, *fields[SEEK_POSITION_ID])
        break  # only the first SeekHead (at the start of the Segment) is in the header
    return None


async def read_cues(reader, header: bytes, segment_data_start: int) -> bytes | None:
    """The whole Cues element, located through the SeekHead or, failing that, the file tail."""
    position = find_cues_position(header, segment_data_start)
    if position is not None:
        start = segment_data_start + position
    else:
        tail_start = max(0, reader.total_size - 2 * 1024 * 1024)
        offset = find_cues_offset(await read_bytes(reader, tail_start, reader.total_size))
        if offset < 0:
            return None
        start = tail_start + offset

    head = await reader.read_window(start, min(start + 12, reader.total_size))
    elem_id, id_len = read_element_id(head, 0)
    size, size_len = read_vint(head, id_len)
    if elem_id != CUES_ID or size_len == 0:
        return None
    return await reader.read_window(start, min(start + id_len + size_len + size, reader.total_size))


def parse_subtitle_cues(cues: bytes, track_numbers: set[int]) -> dict[int, list[SubtitleCue]]:
    """Cue entries of the given tracks that point at an exact block (CueRelativePosition)."""
    found: dict[int, list[SubtitleCue]] = {n: [] for n in track_numbers}
    elem_id, id_len = read_element_id(cues, 0)
    size, size_len = read_vint(cues, id_len)
    if elem_id != CUES_ID:
        return found
    for point_id, point_off, point_size in children(
        cues, id_len + size_len, id_len + size_len + size
    ):
        if point_id != CUE_POINT_ID:
            continue
        time = None
        positions = []
        for child_id, child_off, child_size in children(cues, point_off, point_off + point_size):
            if child_id == CUE_TIME_ID:
                time = read_uint(cues, child_off, child_size)
            elif child_id == CUE_TRACK_POSITIONS_ID:
                positions.append(
                    {
                        i: read_uint(cues, o, s)
                        for i, o, s in children(cues, child_off, child_off + child_size)
                    }
                )
        for p in positions:
            track = p.get(CUE_TRACK_ID)
            if (
                time is not None
                and track in found
                and CUE_CLUSTER_POSITION_ID in p
                and CUE_RELATIVE_POSITION_ID in p
            ):
                found[track].append(
                    SubtitleCue(
                        time=time,
                        cluster_position=p[CUE_CLUSTER_POSITION_ID],
                        relative_position=p[CUE_RELATIVE_POSITION_ID],
                        duration=p.get(CUE_DURATION_ID),
                    )
                )
    return found


async def extract_cued_blocks(
    reader,
    cues_by_track: dict[int, list[SubtitleCue]],
    segment_data_start: int,
    timecode_scale: int,
) -> dict[int, list[SubtitleEvent]]:
    """Read only the indexed subtitle blocks: a small window per block, nearby ones merged."""

    def scale(units: int) -> int:
        return int(units * timecode_scale / 1_000_000)

    # A block starts after its cluster's 4-byte ID, the cluster size VINT (1-8 bytes, the
    # Cues don't say which) and the relative position: one window covers all 8 starts.
    wanted = [
        (segment_data_start + cue.cluster_position + 4 + cue.relative_position, track, cue)
        for track, cues in cues_by_track.items()
        for cue in cues
    ]
    wanted.sort(key=lambda w: w[0])

    windows: list[list[int]] = []
    placed = []  # (window index, base, track, cue)
    for base, track, cue in wanted:
        start, end = base + 1, base + 8 + BLOCK_WINDOW
        if windows and start <= windows[-1][1] + MERGE_GAP and end - windows[-1][0] <= MAX_MERGED:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
        placed.append((len(windows) - 1, base, track, cue))

    semaphore = asyncio.Semaphore(CONCURRENT_READS)

    async def fetch(start: int, end: int) -> bytes:
        async with semaphore:
            return await reader.read_window(start, min(end, reader.total_size))

    data = await asyncio.gather(*(fetch(s, e) for s, e in windows))
    logger.info(
        f"Subtitle cues: {len(placed)} blocks of {len(cues_by_track)} tracks in "
        f"{len(windows)} reads ({sum(map(len, data)) // 1024} KB)"
    )

    # Try the 8 starts in order of how many blocks of the right track each one gives, so bytes
    # of the previous element that happen to look like a block can't win over the real start
    # (muxers use the same VINT length for most or all clusters).
    votes: Counter[int] = Counter()
    for w, base, track, _cue in placed:
        for n in range(1, 9):
            header = _block_header(data[w], base + n - windows[w][0])
            if header and header[1] + header[2] <= len(data[w]) and _parse(data[w], *header, track):
                votes[n] += 1
    order = sorted(range(1, 9), key=lambda n: -votes[n])

    events: dict[int, list[SubtitleEvent]] = {track: [] for track in cues_by_track}
    for w, base, track, cue in placed:
        for n in order:
            header = _block_header(data[w], base + n - windows[w][0])
            if header is None:
                continue
            elem_id, body, size = header
            block = data[w]
            if body + size > len(block):  # longer than the window: read exactly this block
                body_start = windows[w][0] + body
                block, body = await reader.read_window(body_start, body_start + size), 0
            event = _parse(block, elem_id, body, size, track)
            if event:
                event.timestamp_ms = scale(cue.time)
                duration = cue.duration if cue.duration is not None else event.duration_ms
                event.duration_ms = scale(duration) if duration is not None else None
                events[track].append(event)
                break

    for track_events in events.values():
        track_events.sort(key=lambda e: e.timestamp_ms)
    return events


def _block_header(data: bytes, p: int) -> tuple[int, int, int] | None:
    """(element id, body offset, body size) of a SimpleBlock/BlockGroup starting at data[p]."""
    elem_id, id_len = read_element_id(data, p)
    if elem_id not in (SIMPLE_BLOCK_ID, BLOCK_GROUP_ID):
        return None
    size, size_len = read_vint(data, p + id_len)
    if size_len == 0 or size > MAX_BLOCK:
        return None
    return elem_id, p + id_len + size_len, size


def _parse(data: bytes, elem_id: int, body: int, size: int, track: int) -> SubtitleEvent | None:
    if elem_id == SIMPLE_BLOCK_ID:
        return parse_block(data, body, size, 0, (track,))
    parsed = parse_block_group(data, body, size, 0, (track,))
    return parsed[0] if parsed else None


async def read_bytes(reader, start: int, end: int) -> bytes:
    return b"".join([chunk async for chunk in reader.read_range(start, end)])


async def extract_via_cues(
    reader,
    header_data: bytes,
    tracks: Collection[int],
    timecode_scale: int,
) -> tuple[list[SubtitleEvent], bool]:
    """
    Extract subtitle events using MKV Cues index for fast cluster lookup.

    Returns:
        Tuple of (events, cues_found) — cues_found is False if Cues not available.
    """
    events: list[SubtitleEvent] = []
    tail_size = 2 * 1024 * 1024
    header_size = len(header_data)

    if reader.total_size <= header_size + tail_size:
        return events, False

    try:
        tail_data = b""
        start_byte = max(0, reader.total_size - tail_size)
        async for chunk in reader.read_range(start_byte, reader.total_size):
            tail_data += chunk

        cues_offset_relative = find_cues_offset(tail_data)
        if cues_offset_relative < 0:
            return events, False

        logger.debug(f"Found Cues element at tail offset {cues_offset_relative}")

        segment_data_start = find_segment_data_start(header_data)
        cluster_positions = parse_cues_for_clusters(
            tail_data, cues_offset_relative, segment_data_start
        )

        if not cluster_positions:
            return events, False

        logger.info(f"Direct MKV extraction: Found {len(cluster_positions)} clusters via Cues")

        read_ranges = _build_read_ranges(cluster_positions)
        logger.info(f"Plan: {len(read_ranges)} HTTP requests for {len(cluster_positions)} clusters")

        # Parallel fetch + parse
        events = await _parallel_fetch_and_parse(reader, read_ranges, tracks, timecode_scale)
        return events, True

    except Exception as e:
        logger.warning(f"Failed to use Cues for extraction: {e}")
        return events, False


def _scan_chunk_sync(
    chunk_data: bytes,
    tracks: Collection[int],
    timecode_scale: int,
    last: bool = True,
) -> tuple[list[SubtitleEvent], int]:
    """Scan a 10MB chunk for clusters. Pure CPU, no I/O — safe to run in executor.

    Returns the events and where scanning stopped: unless this is the last chunk, a cluster
    cut off by the end of the chunk is left unparsed, for the caller to retry with the next
    chunk appended.
    """
    events: list[SubtitleEvent] = []
    offset = 0
    while offset < len(chunk_data) - 4:
        if chunk_data[offset : offset + 4] == CLUSTER_SIGNATURE:
            cluster_size, size_len = read_vint(chunk_data, offset + 4)
            end = offset + 4 + size_len + cluster_size
            if cluster_size > 50_000_000:  # corrupted VINT, not a real cluster
                offset += 1
                continue
            if not last and (size_len == 0 or end > len(chunk_data)):
                return events, offset
            events.extend(parse_cluster_for_subtitles(chunk_data, offset, tracks, timecode_scale))
            offset = end if size_len else offset + 1
        else:
            offset += 1
    return events, min(offset, len(chunk_data))


async def extract_via_scan(
    reader,
    header_size: int,
    tracks: Collection[int],
    timecode_scale: int,
) -> list[SubtitleEvent]:
    """Fallback: scan file sequentially for clusters containing subtitles."""
    logger.debug("Scanning file for subtitle events (Cues not found)...")
    events: list[SubtitleEvent] = []

    chunk_size = 10 * 1024 * 1024  # 10MB chunks
    file_offset = header_size
    carry = b""  # tail of the previous chunk: a cluster it cut off

    loop = asyncio.get_running_loop()

    while file_offset < reader.total_size:
        read_end = min(file_offset + chunk_size, reader.total_size)
        chunk_data = bytearray(carry)

        try:
            async for chunk in reader.read_range(file_offset, read_end):
                chunk_data += chunk
        except Exception as e:
            logger.warning(f"Failed to read chunk at {file_offset}: {e}")
            break

        chunk_events, stop = await loop.run_in_executor(
            None,
            _scan_chunk_sync,
            bytes(chunk_data),
            tracks,
            timecode_scale,
            read_end >= reader.total_size,
        )
        events.extend(chunk_events)
        carry = bytes(chunk_data[stop:])

        file_offset = read_end

    return events


# --- Private helpers ---


def find_segment_data_start(header_data: bytes) -> int:
    """Find Segment element data start offset in MKV header."""
    segment_signature = bytes([0x18, 0x53, 0x80, 0x67])
    segment_pos = header_data.find(segment_signature)
    if segment_pos >= 0:
        _, seg_id_len = read_element_id(header_data, segment_pos)
        _seg_size, seg_size_len = read_vint(header_data, segment_pos + seg_id_len)
        return segment_pos + seg_id_len + seg_size_len
    return 0


def _build_read_ranges(cluster_positions: list[int]) -> list[tuple[int, int]]:
    """Merge close cluster positions into read ranges to minimize HTTP requests."""
    if not cluster_positions:
        return []

    gap_limit = 10 * 1024 * 1024
    max_merged_size = 30 * 1024 * 1024
    cluster_read_size = 128 * 1024

    read_ranges: list[tuple[int, int]] = []
    current_start = cluster_positions[0]
    current_end = current_start + cluster_read_size

    for i in range(1, len(cluster_positions)):
        pos = cluster_positions[i]
        new_end = max(current_end, pos + cluster_read_size)
        current_size = new_end - current_start

        if (pos < current_end + gap_limit) and (current_size < max_merged_size):
            current_end = new_end
        else:
            read_ranges.append((current_start, current_end))
            current_start = pos
            current_end = pos + cluster_read_size

    read_ranges.append((current_start, current_end))
    return read_ranges


async def _parallel_fetch_and_parse(
    reader,
    read_ranges: list[tuple[int, int]],
    tracks: Collection[int],
    timecode_scale: int,
) -> list[SubtitleEvent]:
    """Fetch cluster data in parallel and parse for subtitle events."""
    events: list[SubtitleEvent] = []

    async with reader.batch_mode():

        async def fetch_range(start: int, end: int, index: int):
            data = bytearray()
            try:
                read_end = min(end, reader.total_size)
                async for chunk in reader.read_range(start, read_end):
                    data.extend(chunk)
                return index, data
            except Exception as e:
                logger.warning(f"Failed to read range {start}-{end}: {e}")
                return index, None

        # Limit to 4 concurrent range reads: each range is up to 30 MB, so
        # 4 × 30 MB = 120 MB in-flight — enough throughput without saturating DC4.
        # 20 was causing thundering-herd timeouts across all active video streams.
        semaphore = asyncio.Semaphore(4)

        async def fetch_with_sem(start: int, end: int, index: int):
            async with semaphore:
                return await fetch_range(start, end, index)

        tasks = [
            fetch_with_sem(start, end, i)
            for i, (start, end) in enumerate(read_ranges)
            if start < reader.total_size
        ]

        results = await asyncio.gather(*tasks) if tasks else []

    # Process results in order
    valid_results = sorted(
        [(idx, data) for idx, data in results if data is not None],
        key=lambda x: x[0],
    )

    for idx, chunk_data in valid_results:
        start, _end = read_ranges[idx]
        chunk_events = await _parse_clusters_in_chunk(
            chunk_data, start, reader, tracks, timecode_scale
        )
        events.extend(chunk_events)

    return events


async def _parse_clusters_in_chunk(
    chunk_data: bytearray,
    abs_start: int,
    reader,
    tracks: Collection[int],
    timecode_scale: int,
) -> list[SubtitleEvent]:
    """Parse all clusters found in a chunk of data."""
    events: list[SubtitleEvent] = []
    curr_offset = 0

    while curr_offset < len(chunk_data) - 4:
        try:
            if chunk_data[curr_offset : curr_offset + 4] != CLUSTER_SIGNATURE:
                next_pos = chunk_data.find(CLUSTER_SIGNATURE, curr_offset + 1)
                if next_pos != -1:
                    curr_offset = next_pos
                else:
                    break
                continue

            id_len = 4
            size_pos = curr_offset + id_len
            if size_pos >= len(chunk_data):
                break

            cluster_size, size_len = read_vint(chunk_data, size_pos)
            if cluster_size > 50_000_000:  # 50 MB hard cap — corrupted VINT guard
                logger.debug(
                    f"Skipping oversized cluster ({cluster_size} bytes) at {abs_start + curr_offset}"
                )
                curr_offset += 1
                continue
            full_cluster_end = size_pos + size_len + cluster_size

            # Fetch missing data for incomplete clusters
            if full_cluster_end > len(chunk_data):
                missing = full_cluster_end - len(chunk_data)
                abs_read_start = abs_start + len(chunk_data)
                abs_read_end = min(abs_read_start + missing, reader.total_size)

                logger.debug(f"Fetching partial cluster: need {missing} bytes at {abs_read_start}")
                try:
                    async for chunk in reader.read_range(abs_read_start, abs_read_end):
                        chunk_data.extend(chunk)
                except Exception as e:
                    logger.warning(f"Failed to extend incomplete cluster: {e}")
                    break

            if full_cluster_end <= len(chunk_data):
                c_data = chunk_data[curr_offset:full_cluster_end]
                try:
                    loop = asyncio.get_running_loop()
                    cluster_events = await loop.run_in_executor(
                        None,
                        parse_cluster_for_subtitles,
                        bytes(c_data),
                        0,
                        tracks,
                        timecode_scale,
                    )
                    if cluster_events:
                        events.extend(cluster_events)
                except Exception as e:
                    logger.debug(f"Failed to parse cluster at {abs_start + curr_offset}: {e}")

                curr_offset = full_cluster_end
            else:
                logger.debug(
                    f"Still incomplete cluster at {abs_start + curr_offset} "
                    f"(need {cluster_size} bytes)"
                )
                curr_offset += 1

        except Exception as e:
            logger.debug(f"Parse error at offset {curr_offset}: {e}")
            curr_offset += 1

    return events
