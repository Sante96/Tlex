"""EBML parsing for MKV subtitle track and cluster extraction.

Parses MKV header to find subtitle tracks, and parses Cluster elements
to extract individual subtitle events (dialog lines).
"""

from dataclasses import dataclass

from loguru import logger

from app.services.mkv_cues import read_element_id, read_uint, read_vint

# EBML Element IDs
TRACKS_ID = 0x1654AE6B
TRACK_ENTRY_ID = 0xAE
TRACK_NUMBER_ID = 0xD7
TRACK_TYPE_ID = 0x83
CODEC_ID_ID = 0x86
CODEC_PRIVATE_ID = 0x63A2
CLUSTER_ID = 0x1F43B675
TIMECODE_ID = 0xE7
SIMPLE_BLOCK_ID = 0xA3
BLOCK_GROUP_ID = 0xA0
BLOCK_ID = 0xA1

TRACK_TYPE_SUBTITLE = 17


@dataclass
class MkvSubtitleTrack:
    """Subtitle track information from MKV header."""

    track_number: int
    codec_id: str  # e.g., "S_TEXT/ASS", "S_TEXT/UTF8"
    codec_private: bytes | None  # ASS header styles


@dataclass
class SubtitleEvent:
    """A single subtitle event/dialog line."""

    timestamp_ms: int
    duration_ms: int | None
    data: bytes


def parse_tracks(data: bytes) -> list[MkvSubtitleTrack]:
    """Parse Tracks element to find subtitle tracks."""
    tracks_signature = bytes([0x16, 0x54, 0xAE, 0x6B])

    search_start = 0
    tracks_offset = -1
    attempt = 0

    while True:
        attempt += 1
        if attempt > 10:
            break

        tracks_offset = data.find(tracks_signature, search_start)

        if tracks_offset < 0:
            if attempt == 1:
                logger.warning(f"Tracks element not found in {len(data)} bytes")
            break

        logger.debug(f"Found Tracks signature at offset {tracks_offset} (attempt {attempt})")

        offset = tracks_offset
        elem_id, id_len = read_element_id(data, offset)

        if elem_id != TRACKS_ID:
            logger.debug(f"  Not a valid Tracks element (ID=0x{elem_id:X})")
            search_start = tracks_offset + 4
            continue

        offset += id_len
        tracks_size, size_len = read_vint(data, offset)

        # Sanity check the size
        if tracks_size <= 0 or tracks_size > 1_000_000:
            search_start = tracks_offset + 4
            continue

        offset += size_len

        tracks = _parse_tracks_content(data, offset, tracks_size)
        if tracks:
            logger.info(
                f"Direct MKV extraction: Found {len(tracks)} subtitle tracks "
                f"at offset {tracks_offset}"
            )
            return tracks

        search_start = tracks_offset + 4

    logger.warning("No valid Tracks element found")
    return []


def _parse_tracks_content(
    data: bytes, offset: int, size: int
) -> list[MkvSubtitleTrack]:
    """Parse the content of a Tracks element."""
    tracks_end = offset + size
    subtitle_tracks: list[MkvSubtitleTrack] = []

    while offset < tracks_end and offset < len(data):
        elem_id, id_len = read_element_id(data, offset)
        if id_len == 0:
            break
        offset += id_len

        elem_size, size_len = read_vint(data, offset)
        if size_len == 0:
            break
        offset += size_len

        if elem_id == TRACK_ENTRY_ID:
            track = _parse_track_entry(data, offset, elem_size)
            if track:
                subtitle_tracks.append(track)

        offset += elem_size

    return subtitle_tracks


def _parse_track_entry(
    data: bytes, offset: int, size: int
) -> MkvSubtitleTrack | None:
    """Parse a single TrackEntry element."""
    end = offset + size

    track_number = None
    track_type = None
    codec_id = None
    codec_private = None

    while offset < end and offset < len(data):
        elem_id, id_len = read_element_id(data, offset)
        if id_len == 0:
            break
        offset += id_len

        elem_size, size_len = read_vint(data, offset)
        if size_len == 0:
            break
        offset += size_len

        if elem_id == TRACK_NUMBER_ID:
            track_number = read_uint(data, offset, elem_size)
        elif elem_id == TRACK_TYPE_ID:
            track_type = read_uint(data, offset, elem_size)
        elif elem_id == CODEC_ID_ID:
            codec_id = data[offset:offset + elem_size].decode("utf-8", errors="ignore")
        elif elem_id == CODEC_PRIVATE_ID:
            codec_private = data[offset:offset + elem_size]

        offset += elem_size

    if track_type == TRACK_TYPE_SUBTITLE and track_number is not None and codec_id:
        logger.debug(f"Found subtitle track {track_number}: {codec_id}")
        return MkvSubtitleTrack(
            track_number=track_number,
            codec_id=codec_id,
            codec_private=codec_private,
        )

    return None


def parse_cluster_for_subtitles(
    data: bytes,
    offset: int,
    target_track: int,
    timecode_scale: int = 1000000,
) -> list[SubtitleEvent]:
    """
    Parse a Cluster element and extract subtitle blocks for a specific track.

    Args:
        data: Raw bytes containing the Cluster
        offset: Offset where Cluster starts
        target_track: Track number to extract
        timecode_scale: Nanoseconds per timestamp unit

    Returns:
        List of subtitle events from this cluster
    """
    events: list[SubtitleEvent] = []

    elem_id, id_len = read_element_id(data, offset)
    if elem_id != CLUSTER_ID:
        return events

    offset += id_len
    cluster_size, size_len = read_vint(data, offset)
    offset += size_len

    cluster_end = offset + cluster_size
    cluster_timecode = 0

    while offset < cluster_end and offset < len(data):
        elem_id, id_len = read_element_id(data, offset)
        if id_len == 0:
            break
        offset += id_len

        elem_size, size_len = read_vint(data, offset)
        if size_len == 0:
            break
        offset += size_len

        if elem_id == TIMECODE_ID:
            cluster_timecode = read_uint(data, offset, elem_size)
        elif elem_id == SIMPLE_BLOCK_ID:
            event = _parse_block(data, offset, elem_size, cluster_timecode, target_track)
            if event:
                event.timestamp_ms = int((event.timestamp_ms * timecode_scale) / 1_000_000)
                events.append(event)
        elif elem_id == BLOCK_GROUP_ID:
            bg_events = _parse_block_group(
                data, offset, elem_size, cluster_timecode, target_track
            )
            for event in bg_events:
                event.timestamp_ms = int((event.timestamp_ms * timecode_scale) / 1_000_000)
                events.append(event)

        offset += elem_size

    return events


def _parse_block(
    data: bytes,
    offset: int,
    size: int,
    cluster_timecode: int,
    target_track: int,
) -> SubtitleEvent | None:
    """Parse a SimpleBlock/Block element."""
    if size < 4:
        return None

    track_num, track_len = read_vint(data, offset)
    if track_num != target_track:
        return None

    rel_offset = offset + track_len
    if rel_offset + 2 > offset + size:
        return None

    relative_time = (data[rel_offset] << 8) | data[rel_offset + 1]
    if relative_time & 0x8000:
        relative_time = relative_time - 0x10000

    data_offset = rel_offset + 3
    payload = data[data_offset:offset + size]

    return SubtitleEvent(
        timestamp_ms=cluster_timecode + relative_time,
        duration_ms=None,
        data=payload,
    )


def _parse_block_group(
    data: bytes,
    offset: int,
    size: int,
    cluster_timecode: int,
    target_track: int,
) -> list[SubtitleEvent]:
    """Parse a BlockGroup element (contains Block + optional duration)."""
    events: list[SubtitleEvent] = []
    end = offset + size
    duration = None
    block_event = None

    while offset < end:
        elem_id, id_len = read_element_id(data, offset)
        if id_len == 0:
            break
        offset += id_len

        elem_size, size_len = read_vint(data, offset)
        if size_len == 0:
            break
        offset += size_len

        if elem_id == BLOCK_ID:
            block_event = _parse_block(
                data, offset, elem_size, cluster_timecode, target_track
            )
        elif elem_id == 0x9B:  # BlockDuration
            duration = read_uint(data, offset, elem_size)

        offset += elem_size

    if block_event:
        block_event.duration_ms = duration
        events.append(block_event)

    return events
