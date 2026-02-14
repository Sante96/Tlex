"""Direct MKV subtitle extraction without FFmpeg.

This module extracts subtitles directly from MKV files by parsing the EBML structure.
It reads only the necessary bytes (header for track info + subtitle data clusters)
instead of downloading the entire file.

Workflow:
1. Read header (~30MB) to get:
   - TrackEntry for subtitle tracks (codec, CodecPrivate)
   - SeekHead to find Clusters position
2. Read Cues (from tail) to find which Clusters contain subtitle data
3. Read only those Clusters and extract subtitle Blocks
4. Reconstruct ASS/SRT file from the data

EBML Element IDs:
- Tracks: 0x1654AE6B
- TrackEntry: 0xAE
- TrackNumber: 0xD7
- TrackType: 0x83 (1=video, 2=audio, 17=subtitle)
- CodecID: 0x86
- CodecPrivate: 0x63A2
- Cluster: 0x1F43B675
- Timecode: 0xE7
- SimpleBlock: 0xA3
- BlockGroup: 0xA0
- Block: 0xA1
"""

import asyncio
from dataclasses import dataclass
from io import BytesIO

from loguru import logger

from app.services.mkv_cues import (
    read_element_id,
    read_uint,
    read_vint,
)

# Additional EBML Element IDs for subtitle extraction
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

# Track types
TRACK_TYPE_SUBTITLE = 17


@dataclass
class SubtitleTrack:
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


def parse_tracks(data: bytes) -> list[SubtitleTrack]:
    """
    Parse Tracks element to find subtitle tracks.

    Args:
        data: Raw bytes containing the Tracks element

    Returns:
        List of subtitle tracks found
    """
    # Find Tracks element (0x1654AE6B)
    tracks_signature = bytes([0x16, 0x54, 0xAE, 0x6B])

    # Search for all occurrences of Tracks signature
    search_start = 0
    tracks_offset = -1
    attempt = 0

    while True:
        attempt += 1
        if attempt > 10:  # Safety limit
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
        if tracks_size <= 0 or tracks_size > 1_000_000:  # Tracks should be < 1MB
            search_start = tracks_offset + 4
            continue

        offset += size_len

        # Try parsing TrackEntry elements
        tracks = _parse_tracks_content(data, offset, tracks_size)

        if tracks:
            logger.info(f"Direct MKV extraction: Found {len(tracks)} subtitle tracks at offset {tracks_offset}")
            return tracks

        # If no tracks found, try next occurrence
        search_start = tracks_offset + 4

    logger.warning("No valid Tracks element found")
    return []


def _parse_tracks_content(data: bytes, offset: int, size: int) -> list[SubtitleTrack]:
    """Parse the content of a Tracks element."""
    tracks_end = offset + size
    subtitle_tracks: list[SubtitleTrack] = []

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

def _parse_track_entry(data: bytes, offset: int, size: int) -> SubtitleTrack | None:
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

    # Only return subtitle tracks
    if track_type == TRACK_TYPE_SUBTITLE and track_number is not None and codec_id:
        logger.debug(f"Found subtitle track {track_number}: {codec_id}")
        return SubtitleTrack(
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

    # Read Cluster header
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
                # Convert timecode to milliseconds
                event.timestamp_ms = int((event.timestamp_ms * timecode_scale) / 1_000_000)
                events.append(event)
        elif elem_id == BLOCK_GROUP_ID:
            # BlockGroup contains Block + optional BlockDuration
            bg_events = _parse_block_group(data, offset, elem_size, cluster_timecode, target_track)
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

    # First byte(s): track number (VINT)
    track_num, track_len = read_vint(data, offset)
    if track_num != target_track:
        return None

    # Next 2 bytes: relative timecode (signed int16)
    rel_offset = offset + track_len
    if rel_offset + 2 > offset + size:
        return None

    relative_time = (data[rel_offset] << 8) | data[rel_offset + 1]
    if relative_time & 0x8000:  # Sign extend
        relative_time = relative_time - 0x10000

    # Skip flags byte
    data_offset = rel_offset + 3

    # Rest is the actual subtitle data
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
            block_event = _parse_block(data, offset, elem_size, cluster_timecode, target_track)
        elif elem_id == 0x9B:  # BlockDuration
            duration = read_uint(data, offset, elem_size)

        offset += elem_size

    if block_event:
        block_event.duration_ms = duration
        events.append(block_event)

    return events


def build_ass_content(track: SubtitleTrack, events: list[SubtitleEvent]) -> bytes:
    """
    Build complete ASS file content from track info and events.

    Args:
        track: Subtitle track with codec_private (ASS header)
        events: List of subtitle events

    Returns:
        Complete ASS file as bytes
    """
    output = BytesIO()

    # Write header from CodecPrivate
    if track.codec_private:
        # CodecPrivate already contains [Script Info], [V4+ Styles], etc.
        # Strip null bytes — MKV containers sometimes pad CodecPrivate with trailing \x00
        header = track.codec_private.replace(b"\x00", b"")
        output.write(header)

        # Ensure header ends with newline
        if not header.endswith(b"\n"):
            output.write(b"\n")

        # Add Events section if not present
        if b"[Events]" not in header:
            output.write(b"\n[Events]\n")
            output.write(b"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    else:
        # Generate minimal ASS header
        output.write(b"[Script Info]\n")
        output.write(b"ScriptType: v4.00+\n")
        output.write(b"\n[V4+ Styles]\n")
        output.write(b"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        output.write(b"Style: Default,Arial,20,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n")
        output.write(b"\n[Events]\n")
        output.write(b"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

    # Sort events by timestamp
    events.sort(key=lambda e: e.timestamp_ms)

    # Write events
    for event in events:
        # Format timestamp as H:MM:SS.cc
        start_ms = event.timestamp_ms
        start_h = start_ms // 3600000
        start_m = (start_ms % 3600000) // 60000
        start_s = (start_ms % 60000) // 1000
        start_cs = (start_ms % 1000) // 10
        start_str = f"{start_h}:{start_m:02d}:{start_s:02d}.{start_cs:02d}"

        # End time
        end_ms = start_ms + (event.duration_ms or 5000)  # Default 5s if no duration
        end_h = end_ms // 3600000
        end_m = (end_ms % 3600000) // 60000
        end_s = (end_ms % 60000) // 1000
        end_cs = (end_ms % 1000) // 10
        end_str = f"{end_h}:{end_m:02d}:{end_s:02d}.{end_cs:02d}"

        # Decode text
        try:
            text = event.data.decode("utf-8")
        except UnicodeDecodeError:
            text = event.data.decode("latin-1", errors="replace")

        # For ASS format from MKV, data is: ReadOrder,Layer,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        # We need to output: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        if "," in text and track.codec_id == "S_TEXT/ASS":
            # Parse the fields: ReadOrder,Layer,Style,Name,MarginL,MarginR,MarginV,Effect,Text
            # The Text field may contain commas, so we split only first 8 commas
            parts = text.split(",", 8)
            if len(parts) >= 9:
                # parts[0] = ReadOrder (skip), parts[1] = Layer, parts[2] = Style, etc.
                layer = parts[1]
                style = parts[2]
                name = parts[3]
                margin_l = parts[4]
                margin_r = parts[5]
                margin_v = parts[6]
                effect = parts[7]
                dialogue_text = parts[8]

                line = f"Dialogue: {layer},{start_str},{end_str},{style},{name},{margin_l},{margin_r},{margin_v},{effect},{dialogue_text}\n"
            else:
                # Fallback: not enough fields, use as-is with timestamps
                line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"
        else:
            # Plain text (SRT-style) - wrap in Dialogue
            line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"

        output.write(line.encode("utf-8"))

    return output.getvalue()


def build_srt_content(events: list[SubtitleEvent]) -> bytes:
    """Build SRT file content from events."""
    output = BytesIO()

    events.sort(key=lambda e: e.timestamp_ms)

    for i, event in enumerate(events, 1):
        # Index
        output.write(f"{i}\n".encode())

        # Timestamps: HH:MM:SS,mmm --> HH:MM:SS,mmm
        start_ms = event.timestamp_ms
        start_h = start_ms // 3600000
        start_m = (start_ms % 3600000) // 60000
        start_s = (start_ms % 60000) // 1000
        start_sms = start_ms % 1000

        end_ms = start_ms + (event.duration_ms or 5000)
        end_h = end_ms // 3600000
        end_m = (end_ms % 3600000) // 60000
        end_s = (end_ms % 60000) // 1000
        end_sms = end_ms % 1000

        output.write(f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_sms:03d} --> ".encode())
        output.write(f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_sms:03d}\n".encode())

        # Text
        try:
            text = event.data.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = event.data.decode("latin-1", errors="replace").strip()

        output.write(f"{text}\n\n".encode())

    return output.getvalue()


async def extract_subtitle_direct(
    reader,  # VirtualReader
    track_index: int = 0,
    output_format: str = "ass",
) -> bytes | None:
    """
    Extract subtitle directly from MKV file using VirtualReader.

    This is MUCH faster than FFmpeg because we only read:
    1. Header (~30MB) to get track info
    2. Specific clusters containing subtitle data

    Args:
        reader: VirtualReader instance for the media
        track_index: Which subtitle track to extract (0-based)
        output_format: "ass" or "srt"

    Returns:
        Subtitle file content as bytes, or None if extraction failed
    """
    from app.services.mkv_cues import extract_timecode_scale

    logger.info(f"Starting direct subtitle extraction: track={track_index}, format={output_format}")

    # 1. Read header to get tracks info
    # We need ~30MB to reliably get Tracks element
    header_size = 31_457_280  # 30MB
    header_data = b""

    try:
        async for chunk in reader.read_range(0, header_size):
            header_data += chunk
    except Exception as e:
        logger.error(f"Failed to read MKV header: {e}")
        return None

    logger.debug(f"Read {len(header_data)} bytes from MKV header")

    # 2. Parse tracks to find subtitle tracks
    subtitle_tracks = parse_tracks(header_data)

    if not subtitle_tracks:
        logger.warning("No subtitle tracks found in MKV")
        return None

    if track_index >= len(subtitle_tracks):
        logger.warning(f"Track index {track_index} out of range (have {len(subtitle_tracks)} tracks)")
        return None

    target_track = subtitle_tracks[track_index]
    logger.info(f"Extracting track {target_track.track_number}: {target_track.codec_id}")

    # 3. Get timecode scale
    timecode_scale = extract_timecode_scale(header_data)

    events: list[SubtitleEvent] = []
    cluster_signature = bytes([0x1F, 0x43, 0xB6, 0x75])

    # 4. Try to find Cues (index) to locate clusters quickly
    # Cues are usually at the end of the file
    cues_found = False

    # Read last 2MB to find Cues
    tail_size = 2 * 1024 * 1024
    if reader.total_size > header_size + tail_size:
        try:
            tail_data = b""
            start_byte = max(0, reader.total_size - tail_size)
            async for chunk in reader.read_range(start_byte, reader.total_size):
                tail_data += chunk

            from app.services.mkv_cues import find_cues_offset, parse_cues_for_clusters

            cues_offset_relative = find_cues_offset(tail_data)
            if cues_offset_relative >= 0:
                logger.debug(f"Found Cues element at tail offset {cues_offset_relative}")
                start_byte + cues_offset_relative

                # We need segment offset (usually just after EBML header)
                # But for simplicity, we assume cluster positions are relative to start of file
                # or we rely on the parser to give us good offsets.
                # Actually, cluster positions are relative to Segment Data start.
                # Tracks parsing gave us 'tracks_signature' offset. Segment is usually before that.
                # Let's find Segment element start.
                segment_signature = bytes([0x18, 0x53, 0x80, 0x67])
                segment_pos = header_data.find(segment_signature)
                if segment_pos >= 0:
                     # Skip Segment ID (4) + Size (vint)
                     # But we don't know size length easily without parsing.
                     # However, safe bet is to add a small offset, or use 0 if relative to file.
                     # Typically, Cluster positions are relative to Segment Data start.
                     # Let's try to parse Segment header properly.
                     seg_id, seg_id_len = read_element_id(header_data, segment_pos)
                     seg_size, seg_size_len = read_vint(header_data, segment_pos + seg_id_len)
                     segment_data_start = segment_pos + seg_id_len + seg_size_len
                else:
                    segment_data_start = 0

                cluster_positions = parse_cues_for_clusters(tail_data, cues_offset_relative, segment_data_start)

                if cluster_positions:
                    logger.info(f"Direct MKV extraction: Found {len(cluster_positions)} clusters as entry points via Cues")
                    cues_found = True

                    # Optimization: Surgical Reads
                    # Only merge requests if they are very close (e.g. < 1MB gap)
                    # This avoids reading large video chunks between subtitles
                    read_ranges = []
                    if cluster_positions:
                        # 10MB gap limit - Reduce latency by merging more
                        gap_limit = 10 * 1024 * 1024
                        # Safety: Don't create chunks larger than 30MB to preserve RAM
                        max_merged_size = 30 * 1024 * 1024

                        # Initial read size for cluster header + some data
                        # Subtitle clusters can be variable, 128KB is a safer start
                        cluster_read_size = 128 * 1024

                        current_start = cluster_positions[0]
                        current_end = current_start + cluster_read_size

                        for i in range(1, len(cluster_positions)):
                            pos = cluster_positions[i]

                            # Check potential new size
                            new_end = max(current_end, pos + cluster_read_size)
                            current_size = new_end - current_start

                            # If gaps is small enough AND total size is safe, merge
                            if (pos < current_end + gap_limit) and (current_size < max_merged_size):
                                current_end = new_end
                            else:
                                read_ranges.append((current_start, current_end))
                                current_start = pos
                                current_end = pos + cluster_read_size

                        read_ranges.append((current_start, current_end))

                    logger.info(f"Plan: {len(read_ranges)} HTTP requests for {len(cluster_positions)} clusters (Gap limit: 1MB)")

                    # Optimization: Run in Parallel (Batch Mode)
                    # We use batch_mode() to hold the worker and DB session open
                    async with reader.batch_mode():

                        # Helper for parallel fetching
                        async def fetch_range(start, end, index):
                            data = bytearray()
                            try:
                                # Clamp end
                                read_end = min(end, reader.total_size)
                                async for chunk in reader.read_range(start, read_end):
                                    data.extend(chunk)
                                return index, data
                            except Exception as e:
                                logger.warning(f"Failed to read range {start}-{end}: {e}")
                                return index, None

                        # Configure concurrency
                        semaphore = asyncio.Semaphore(20) # 20 concurrent requests

                        async def fetch_with_sem(start, end, index):
                            async with semaphore:
                                return await fetch_range(start, end, index)

                        # Create tasks
                        tasks = []
                        for i, (start, end) in enumerate(read_ranges):
                            if start >= reader.total_size:
                                continue
                            tasks.append(fetch_with_sem(start, end, i))

                        # Execute all
                        if tasks:
                            results = await asyncio.gather(*tasks)
                        else:
                            results = []

                    # Process results sequentially to maintain order and logic
                    # Sort by index just in case (gather preserves order but safety first)
                    # results is list of (index, data)
                    valid_results = [r for r in results if r is not None and r[1] is not None]

                    # We iterate over the original Read Ranges logic using the fetched data
                    # But wait, our original loop also did "Dynamic Extension" (fixing incomplete clusters).
                    # If we fetch in parallel, we can't easily extend unless we do it inside the task?
                    # The "Dynamic Extension" required accessing reader again.
                    # Use batch_mode() inside the task is fine (it's rentrant/shared).
                    # Actually, if we use batch_mode() globally, the tasks share it.

                    # The original parsing loop logic was:
                    # 1. Read chunk
                    # 2. Parse
                    # 3. If incomplete -> READ MORE immediately

                    # To support this in parallel, we need the task to handle the "READ MORE" part.
                    # But the task currently just returns raw bytes.
                    # We have two options:
                    # A) Just fetch initial ranges in parallel, then process sequentially. If incomplete, fetch synchronously (fast enough?).
                    # B) Move parsing inside the task (complex, needs state).

                    # Let's go with A) Parallel Fetch Initial -> Sequential Parse & Fix.
                    # Since "Incomplete Cluster" is rare now (we buffed read size to 128KB),
                    # fixing it sequentially is fine. The bulk of time is the 950 initial requests.

                    # Sort results by index to process them in the original order of read_ranges
                    valid_results.sort(key=lambda x: x[0])

                    for idx, chunk_data in valid_results:
                        start, end = read_ranges[idx] # Get original start for logging/context

                        # Parse clusters in this chunk
                        # Using memoryview for zero-copy slicing would be best, but data is small enough now

                        # Parse clusters in this chunk
                        curr_offset = 0

                        while curr_offset < len(chunk_data) - 4:
                            # 1. Find cluster signature
                            try:
                                # Quick check first 4 bytes
                                if chunk_data[curr_offset:curr_offset+4] == cluster_signature:
                                    # Found a cluster
                                    id_len = 4 # signature length

                                    # Parse size
                                    size_pos = curr_offset + id_len
                                    if size_pos >= len(chunk_data):
                                        break

                                    cluster_size, size_len = read_vint(chunk_data, size_pos)

                                    # Check if we have the full cluster
                                    full_cluster_end = size_pos + size_len + cluster_size

                                    if full_cluster_end > len(chunk_data):
                                        # Incomplete cluster!
                                        # We need to fetch the rest of it immediately
                                        missing = full_cluster_end - len(chunk_data)
                                        abs_read_start = start + len(chunk_data)
                                        abs_read_end = min(abs_read_start + missing, reader.total_size)

                                        logger.debug(f"Fetching partial cluster: need {missing} bytes at {abs_read_start}")

                                        try:
                                            async for chunk in reader.read_range(abs_read_start, abs_read_end):
                                                chunk_data.extend(chunk)
                                        except Exception as e:
                                            logger.warning(f"Failed to extend incomplete cluster: {e}")
                                            break # Can't fix it, stop parsing this chunk

                                    # Check again if we have enough data (we should now)
                                    if full_cluster_end <= len(chunk_data):
                                        # We have the full cluster data
                                        c_data = chunk_data[curr_offset:full_cluster_end]

                                        try:
                                            cluster_events = parse_cluster_for_subtitles(
                                                c_data, 0, target_track.track_number, timecode_scale
                                            )
                                            if cluster_events:
                                                events.extend(cluster_events)
                                        except Exception as e:
                                            logger.debug(f"Failed to parse cluster at {start+curr_offset}: {e}")

                                        # Advance past this cluster
                                        curr_offset = full_cluster_end
                                    else:
                                        # Still not enough? Must be EOF or read error
                                        logger.debug(f"Still incomplete cluster at {start+curr_offset} (need {cluster_size} bytes)")
                                        curr_offset += 1
                                else:
                                    # Not a cluster start, move forward
                                    # Optimization: use find to skip bytes
                                    next_pos = chunk_data.find(cluster_signature, curr_offset + 1)
                                    if next_pos != -1:
                                        curr_offset = next_pos
                                    else:
                                        break # No more clusters in this chunk

                            except Exception as e:
                                logger.debug(f"Parse error at offset {curr_offset}: {e}")
                                curr_offset += 1

        except Exception as e:
            logger.warning(f"Failed to use Cues for extraction: {e}")

    # 5. If we need more events (and didn't use Cues), scan chunks
    if not cues_found and (not events or len(events) < 1000):
            logger.debug("Scanning file for subtitle events (Cues not found)...")

            chunk_size = 10 * 1024 * 1024  # 10MB chunks
            file_offset = header_size

            # Read until end of file
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
                    if chunk_data[offset:offset+4] == cluster_signature:
                        cluster_events = parse_cluster_for_subtitles(
                            chunk_data, offset, target_track.track_number, timecode_scale
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

    if not events:
        logger.warning("No subtitle events found")
        return None

    logger.info(f"Total {len(events)} subtitle events extracted")

    # 6. Build output file
    if output_format == "ass":
        return build_ass_content(target_track, events)
    else:
        return build_srt_content(events)
