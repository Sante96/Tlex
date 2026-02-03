"""MKV Cues parser for fast keyframe extraction.

MKV files store keyframe indices in the "Cues" element, typically at the end
of the file. This allows extracting keyframe timestamps by reading only
a small portion of the file (~1-2MB) instead of the entire file.

EBML Element IDs used:
- Segment: 0x18538067
- SegmentInfo: 0x1549A966
- TimecodeScale: 0x2AD7B1
- Cues: 0x1C53BB6B
- CuePoint: 0xBB
- CueTime: 0xB3
- CueTrackPositions: 0xB7
- CueTrack: 0xF7
"""

from dataclasses import dataclass

import httpx
from loguru import logger


@dataclass
class CuePoint:
    """A single cue point (keyframe) in MKV."""
    time_ms: int  # Timestamp in milliseconds
    track: int = 1  # Track number (usually 1 for video)


def read_vint(data: bytes, offset: int) -> tuple[int, int]:
    """
    Read EBML variable-length integer.

    Returns (value, bytes_consumed).
    """
    if offset >= len(data):
        return 0, 0

    first_byte = data[offset]

    # Determine length from leading bits
    if first_byte & 0x80:  # 1 byte
        return first_byte & 0x7F, 1
    elif first_byte & 0x40:  # 2 bytes
        if offset + 1 >= len(data):
            return 0, 0
        return ((first_byte & 0x3F) << 8) | data[offset + 1], 2
    elif first_byte & 0x20:  # 3 bytes
        if offset + 2 >= len(data):
            return 0, 0
        return ((first_byte & 0x1F) << 16) | (data[offset + 1] << 8) | data[offset + 2], 3
    elif first_byte & 0x10:  # 4 bytes
        if offset + 3 >= len(data):
            return 0, 0
        return ((first_byte & 0x0F) << 24) | (data[offset + 1] << 16) | (data[offset + 2] << 8) | data[offset + 3], 4
    elif first_byte & 0x08:  # 5 bytes
        if offset + 4 >= len(data):
            return 0, 0
        val = ((first_byte & 0x07) << 32) | (data[offset + 1] << 24) | (data[offset + 2] << 16) | (data[offset + 3] << 8) | data[offset + 4]
        return val, 5
    elif first_byte & 0x04:  # 6 bytes
        if offset + 5 >= len(data):
            return 0, 0
        val = ((first_byte & 0x03) << 40) | (data[offset + 1] << 32) | (data[offset + 2] << 24) | (data[offset + 3] << 16) | (data[offset + 4] << 8) | data[offset + 5]
        return val, 6
    elif first_byte & 0x02:  # 7 bytes
        if offset + 6 >= len(data):
            return 0, 0
        val = ((first_byte & 0x01) << 48) | (data[offset + 1] << 40) | (data[offset + 2] << 32) | (data[offset + 3] << 24) | (data[offset + 4] << 16) | (data[offset + 5] << 8) | data[offset + 6]
        return val, 7
    elif first_byte & 0x01:  # 8 bytes
        if offset + 7 >= len(data):
            return 0, 0
        val = (data[offset + 1] << 48) | (data[offset + 2] << 40) | (data[offset + 3] << 32) | (data[offset + 4] << 24) | (data[offset + 5] << 16) | (data[offset + 6] << 8) | data[offset + 7]
        return val, 8

    return 0, 0


def read_element_id(data: bytes, offset: int) -> tuple[int, int]:
    """
    Read EBML element ID.

    Returns (element_id, bytes_consumed).
    """
    if offset >= len(data):
        return 0, 0

    first_byte = data[offset]

    if first_byte & 0x80:  # 1 byte ID
        return first_byte, 1
    elif first_byte & 0x40:  # 2 byte ID
        if offset + 1 >= len(data):
            return 0, 0
        return (first_byte << 8) | data[offset + 1], 2
    elif first_byte & 0x20:  # 3 byte ID
        if offset + 2 >= len(data):
            return 0, 0
        return (first_byte << 16) | (data[offset + 1] << 8) | data[offset + 2], 3
    elif first_byte & 0x10:  # 4 byte ID
        if offset + 3 >= len(data):
            return 0, 0
        return (first_byte << 24) | (data[offset + 1] << 16) | (data[offset + 2] << 8) | data[offset + 3], 4

    return 0, 0


def read_uint(data: bytes, offset: int, length: int) -> int:
    """Read unsigned integer of given length."""
    if offset + length > len(data):
        return 0

    value = 0
    for i in range(length):
        value = (value << 8) | data[offset + i]
    return value


# EBML Element IDs
SEGMENT_INFO_ID = 0x1549A966
TIMECODE_SCALE_ID = 0x2AD7B1
CUES_ID = 0x1C53BB6B
CUE_POINT_ID = 0xBB
CUE_TIME_ID = 0xB3
CUE_TRACK_POSITIONS_ID = 0xB7
CUE_TRACK_ID = 0xF7

# Default timecode scale: 1000000 ns = 1ms per unit
DEFAULT_TIMECODE_SCALE = 1000000


def find_cues_offset(data: bytes) -> int:
    """
    Find the offset of the Cues element in the data.

    Searches for the Cues element ID (0x1C53BB6B).
    """
    # Cues ID as bytes: 0x1C 0x53 0xBB 0x6B
    cues_signature = bytes([0x1C, 0x53, 0xBB, 0x6B])

    idx = data.find(cues_signature)
    return idx


def extract_timecode_scale(data: bytes) -> int:
    """
    Extract TimecodeScale from MKV Segment Info.

    TimecodeScale defines nanoseconds per timestamp unit.
    Default is 1000000 (1ms per unit).

    Args:
        data: Raw bytes from the beginning of the MKV file

    Returns:
        TimecodeScale in nanoseconds (default 1000000 if not found)
    """
    # Find Segment Info element (0x1549A966 = bytes 15 49 A9 66)
    info_signature = bytes([0x15, 0x49, 0xA9, 0x66])
    info_offset = data.find(info_signature)

    if info_offset < 0:
        logger.debug("Segment Info not found, using default timecode scale")
        return DEFAULT_TIMECODE_SCALE

    offset = info_offset
    elem_id, id_len = read_element_id(data, offset)
    if elem_id != SEGMENT_INFO_ID:
        return DEFAULT_TIMECODE_SCALE

    offset += id_len
    info_size, size_len = read_vint(data, offset)
    offset += size_len

    info_end = offset + info_size

    # Search for TimecodeScale within Segment Info
    while offset < info_end and offset < len(data):
        inner_id, inner_id_len = read_element_id(data, offset)
        if inner_id_len == 0:
            break
        offset += inner_id_len

        inner_size, inner_size_len = read_vint(data, offset)
        if inner_size_len == 0:
            break
        offset += inner_size_len

        if inner_id == TIMECODE_SCALE_ID:
            timecode_scale = read_uint(data, offset, inner_size)
            logger.info(f"Found TimecodeScale: {timecode_scale} ns")
            return timecode_scale

        offset += inner_size

    logger.debug("TimecodeScale not found in Segment Info, using default")
    return DEFAULT_TIMECODE_SCALE


def parse_cues(
    data: bytes,
    offset: int,
    timecode_scale: int = 1000000,
    video_track: int = 1,
) -> list[float]:
    """
    Parse Cues element and extract keyframe timestamps for video track only.

    Args:
        data: Raw bytes containing the Cues element
        offset: Offset where Cues element starts
        timecode_scale: Nanoseconds per timestamp unit (default: 1ms)
        video_track: Video track number to filter (default: 1)

    Returns:
        List of keyframe timestamps in seconds (video track only)
    """
    keyframes: list[float] = []

    # Read Cues element header
    element_id, id_len = read_element_id(data, offset)
    if element_id != CUES_ID:
        return keyframes

    offset += id_len
    cues_size, size_len = read_vint(data, offset)
    offset += size_len

    cues_end = offset + cues_size

    # Parse CuePoint elements
    while offset < cues_end and offset < len(data):
        elem_id, id_len = read_element_id(data, offset)
        if id_len == 0:
            break
        offset += id_len

        elem_size, size_len = read_vint(data, offset)
        if size_len == 0:
            break
        offset += size_len

        if elem_id == CUE_POINT_ID:
            # Parse CuePoint to extract CueTime and CueTrack
            cue_end = offset + elem_size
            cue_time = None
            cue_track = None

            while offset < cue_end and offset < len(data):
                inner_id, inner_id_len = read_element_id(data, offset)
                if inner_id_len == 0:
                    break
                offset += inner_id_len

                inner_size, inner_size_len = read_vint(data, offset)
                if inner_size_len == 0:
                    break
                offset += inner_size_len

                if inner_id == CUE_TIME_ID:
                    # CueTime is the timestamp in timecode units
                    cue_time = read_uint(data, offset, inner_size)
                elif inner_id == CUE_TRACK_POSITIONS_ID:
                    # Parse CueTrackPositions to get track number
                    track_end = offset + inner_size
                    track_offset = offset
                    while track_offset < track_end:
                        track_id, track_id_len = read_element_id(data, track_offset)
                        if track_id_len == 0:
                            break
                        track_offset += track_id_len
                        track_size, track_size_len = read_vint(data, track_offset)
                        if track_size_len == 0:
                            break
                        track_offset += track_size_len
                        if track_id == CUE_TRACK_ID:
                            cue_track = read_uint(data, track_offset, track_size)
                            break
                        track_offset += track_size

                offset += inner_size

            # Only add keyframe if it's for the video track
            if cue_time is not None and cue_track == video_track:
                time_seconds = (cue_time * timecode_scale) / 1_000_000_000
                keyframes.append(time_seconds)

            offset = cue_end
        else:
            offset += elem_size

    return keyframes


async def extract_keyframes_from_url(
    url: str,
    total_size: int | None = None,
    head_read_size: int = 1 * 1024 * 1024,  # 1MB for header (TimecodeScale)
    tail_read_size: int = 2 * 1024 * 1024,  # 2MB for Cues
) -> list[float]:
    """
    Extract keyframes from MKV file by reading header and Cues section.

    Reads:
    - First ~1MB to get TimecodeScale from Segment Info
    - Last ~2MB to get Cues (keyframe indices)

    Args:
        url: URL to the MKV file (must support Range requests)
        total_size: Total file size (if known, avoids HEAD request)
        head_read_size: Bytes to read from start for TimecodeScale
        tail_read_size: Bytes to read from end for Cues

    Returns:
        List of keyframe timestamps in seconds (sorted)
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Get file size if not provided
        if total_size is None:
            head_response = await client.head(url)
            content_length = head_response.headers.get("content-length")
            if content_length:
                total_size = int(content_length)
            else:
                logger.warning("Cannot determine file size for MKV Cues extraction")
                return []

        # 1. Read header to get TimecodeScale
        header_headers = {"Range": f"bytes=0-{head_read_size - 1}"}
        header_response = await client.get(url, headers=header_headers)

        timecode_scale = DEFAULT_TIMECODE_SCALE
        if header_response.status_code in (200, 206):
            header_data = header_response.content
            logger.info(f"Read {len(header_data)} bytes from MKV header")
            timecode_scale = extract_timecode_scale(header_data)
        else:
            logger.warning(f"Failed to read MKV header: HTTP {header_response.status_code}")

        # 2. Read tail to get Cues
        start_byte = max(0, total_size - tail_read_size)
        tail_headers = {"Range": f"bytes={start_byte}-{total_size - 1}"}
        tail_response = await client.get(url, headers=tail_headers)

        if tail_response.status_code not in (200, 206):
            logger.warning(f"Failed to read MKV tail: HTTP {tail_response.status_code}")
            return []

        tail_data = tail_response.content
        logger.info(f"Read {len(tail_data)} bytes from MKV tail for Cues parsing")

        # Find and parse Cues with correct timecode_scale
        cues_offset = find_cues_offset(tail_data)
        if cues_offset < 0:
            logger.warning("Cues element not found in MKV tail")
            return []

        logger.info(f"Found Cues at offset {cues_offset} in tail data")

        keyframes = parse_cues(tail_data, cues_offset, timecode_scale)
        keyframes.sort()

        logger.info(f"Extracted {len(keyframes)} keyframes from MKV Cues (scale={timecode_scale}ns)")
        return keyframes


# For testing
if __name__ == "__main__":
    import asyncio

    async def test():
        # Test with a local file
        url = "http://127.0.0.1:8000/api/v1/stream/raw/78"
        keyframes = await extract_keyframes_from_url(url)
        print(f"Found {len(keyframes)} keyframes")
        if keyframes:
            print(f"First 10: {keyframes[:10]}")
            print(f"Last 10: {keyframes[-10:]}")

    asyncio.run(test())
