"""Direct MKV subtitle extraction without FFmpeg.

Extracts subtitles directly from MKV files by parsing EBML structure.
Reads only the necessary bytes (header + subtitle clusters) instead of
downloading the entire file.

Workflow:
1. Read header (~30MB) for track info
2. Read Cues (from tail) to find subtitle cluster positions
3. Read only those clusters and extract subtitle blocks
4. Reconstruct ASS/SRT file from the data
"""

from loguru import logger

from app.services.subtitles.builders import build_ass_content, build_srt_content
from app.services.subtitles.cluster_reader import extract_via_cues, extract_via_scan
from app.services.subtitles.ebml_parser import parse_tracks

HEADER_SIZE = 31_457_280  # 30MB — enough to reliably get Tracks element


async def extract_subtitle_direct(
    reader,
    track_index: int = 0,
    output_format: str = "ass",
) -> bytes | None:
    """
    Extract subtitle directly from MKV file using VirtualReader.

    Much faster than FFmpeg — only reads header + subtitle clusters.

    Args:
        reader: VirtualReader instance for the media
        track_index: Which subtitle track to extract (0-based)
        output_format: "ass" or "srt"

    Returns:
        Subtitle file content as bytes, or None if extraction failed
    """
    from app.services.mkv_cues import extract_timecode_scale

    logger.info(f"Starting direct subtitle extraction: track={track_index}, format={output_format}")

    # 1. Read header for track info
    header_data = b""
    try:
        async for chunk in reader.read_range(0, HEADER_SIZE):
            header_data += chunk
    except Exception as e:
        logger.error(f"Failed to read MKV header: {e}")
        return None

    logger.debug(f"Read {len(header_data)} bytes from MKV header")

    # 2. Parse tracks
    subtitle_tracks = parse_tracks(header_data)
    if not subtitle_tracks:
        logger.warning("No subtitle tracks found in MKV")
        return None

    if track_index >= len(subtitle_tracks):
        logger.warning(
            f"Track index {track_index} out of range (have {len(subtitle_tracks)} tracks)"
        )
        return None

    target_track = subtitle_tracks[track_index]
    logger.info(f"Extracting track {target_track.track_number}: {target_track.codec_id}")

    # 3. Get timecode scale
    timecode_scale = extract_timecode_scale(header_data)

    # 4. Extract events — try Cues first, fallback to sequential scan
    events, cues_found = await extract_via_cues(
        reader, header_data, target_track.track_number, timecode_scale
    )

    if not cues_found and (not events or len(events) < 1000):
        events = await extract_via_scan(
            reader, HEADER_SIZE, target_track.track_number, timecode_scale
        )

    if not events:
        logger.warning("No subtitle events found")
        return None

    logger.info(f"Total {len(events)} subtitle events extracted")

    # 5. Build output file
    if output_format == "ass":
        return build_ass_content(target_track, events)
    else:
        return build_srt_content(events)
