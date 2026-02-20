"""Cluster reading strategies for MKV subtitle extraction.

Two strategies:
1. Cues-based: Use MKV Cues index to locate clusters, fetch in parallel.
2. Sequential scan: Fallback when Cues are not available.
"""

import asyncio

from loguru import logger

from app.services.mkv_cues import (
    find_cues_offset,
    parse_cues_for_clusters,
    read_element_id,
    read_vint,
)
from app.services.subtitles.ebml_parser import SubtitleEvent, parse_cluster_for_subtitles

CLUSTER_SIGNATURE = bytes([0x1F, 0x43, 0xB6, 0x75])


async def extract_via_cues(
    reader,
    header_data: bytes,
    target_track_number: int,
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

        segment_data_start = _find_segment_data_start(header_data)
        cluster_positions = parse_cues_for_clusters(
            tail_data, cues_offset_relative, segment_data_start
        )

        if not cluster_positions:
            return events, False

        logger.info(
            f"Direct MKV extraction: Found {len(cluster_positions)} clusters via Cues"
        )

        read_ranges = _build_read_ranges(cluster_positions)
        logger.info(
            f"Plan: {len(read_ranges)} HTTP requests for "
            f"{len(cluster_positions)} clusters"
        )

        # Parallel fetch + parse
        events = await _parallel_fetch_and_parse(
            reader, read_ranges, target_track_number, timecode_scale
        )
        return events, True

    except Exception as e:
        logger.warning(f"Failed to use Cues for extraction: {e}")
        return events, False


async def extract_via_scan(
    reader,
    header_size: int,
    target_track_number: int,
    timecode_scale: int,
) -> list[SubtitleEvent]:
    """Fallback: scan file sequentially for clusters containing subtitles."""
    logger.debug("Scanning file for subtitle events (Cues not found)...")
    events: list[SubtitleEvent] = []

    chunk_size = 10 * 1024 * 1024  # 10MB chunks
    file_offset = header_size

    while file_offset < reader.total_size:
        read_end = min(file_offset + chunk_size, reader.total_size)
        chunk_data = b""

        try:
            async for chunk in reader.read_range(file_offset, read_end):
                chunk_data += chunk
        except Exception as e:
            logger.warning(f"Failed to read chunk at {file_offset}: {e}")
            break

        # Find clusters in this chunk
        offset = 0
        while offset < len(chunk_data) - 4:
            if chunk_data[offset:offset + 4] == CLUSTER_SIGNATURE:
                cluster_events = parse_cluster_for_subtitles(
                    chunk_data, offset, target_track_number, timecode_scale
                )
                events.extend(cluster_events)

                try:
                    elem_id, id_len = read_element_id(chunk_data, offset)
                    offset += id_len
                    cluster_size, size_len = read_vint(chunk_data, offset)
                    offset += size_len + cluster_size
                except Exception:
                    offset += 1
            else:
                offset += 1

        file_offset = read_end

    return events


# --- Private helpers ---


def _find_segment_data_start(header_data: bytes) -> int:
    """Find Segment element data start offset in MKV header."""
    segment_signature = bytes([0x18, 0x53, 0x80, 0x67])
    segment_pos = header_data.find(segment_signature)
    if segment_pos >= 0:
        seg_id, seg_id_len = read_element_id(header_data, segment_pos)
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
    target_track_number: int,
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

        semaphore = asyncio.Semaphore(20)

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
        chunk_events = _parse_clusters_in_chunk(
            chunk_data, start, reader, target_track_number, timecode_scale
        )
        events.extend(chunk_events)

    return events


async def _parse_clusters_in_chunk(
    chunk_data: bytearray,
    abs_start: int,
    reader,
    target_track_number: int,
    timecode_scale: int,
) -> list[SubtitleEvent]:
    """Parse all clusters found in a chunk of data."""
    events: list[SubtitleEvent] = []
    curr_offset = 0

    while curr_offset < len(chunk_data) - 4:
        try:
            if chunk_data[curr_offset:curr_offset + 4] != CLUSTER_SIGNATURE:
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
                    cluster_events = parse_cluster_for_subtitles(
                        c_data, 0, target_track_number, timecode_scale
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
