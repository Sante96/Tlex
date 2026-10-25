"""Direct MKV subtitle extraction without FFmpeg.

Extracts subtitles directly from MKV files by parsing EBML structure.
Reads only the necessary bytes instead of downloading the entire file.

Workflow:
1. Read the header (1 MB) for track info
2. Read the Cues (located through the SeekHead) and keep the subtitle block entries
3. Read only those blocks, a few KB each, for every text track at once
4. Tracks without such entries: read the clusters (via cluster Cues, else a scan)
"""

from loguru import logger

from app.services.mkv_cues import extract_timecode_scale
from app.services.subtitles.cluster_reader import (
    extract_cued_blocks,
    extract_via_cues,
    extract_via_scan,
    find_segment_data_start,
    parse_subtitle_cues,
    read_bytes,
    read_cues,
)
from app.services.subtitles.ebml_parser import MkvSubtitleTrack, SubtitleEvent, parse_tracks

HEADER_SIZE = 1024 * 1024  # Tracks sit in the first KBs
FALLBACK_HEADER_SIZE = 31_457_280  # 30 MB, for files that put them later
TEXT_CODECS = ("S_TEXT/", "S_ASS", "S_SSA")  # not PGS/VobSub images


async def extract_all_subtitles(
    reader,
) -> list[tuple[MkvSubtitleTrack, list[SubtitleEvent] | None]] | None:
    """Every subtitle track of the MKV, in file order, with its events.

    Image tracks get None instead of events: they can't become ASS/SRT.
    Returns None if the header can't be read; later read errors propagate.
    """
    async with reader.batch_mode():
        try:
            header = await read_bytes(reader, 0, HEADER_SIZE)
            tracks = parse_tracks(header)
            if not tracks:
                header = await read_bytes(reader, 0, FALLBACK_HEADER_SIZE)
                tracks = parse_tracks(header)
        except Exception as e:
            logger.error(f"Failed to read MKV header: {e}")
            return None

        text = {t.track_number for t in tracks if t.codec_id.startswith(TEXT_CODECS)}
        events: dict[int, list[SubtitleEvent]] = {}
        if text:
            timecode_scale = extract_timecode_scale(header)
            segment_data_start = find_segment_data_start(header)

            cues = await read_cues(reader, header, segment_data_start)
            cued = {n: c for n, c in parse_subtitle_cues(cues, text).items() if c} if cues else {}
            if cued:
                events = await extract_cued_blocks(reader, cued, segment_data_start, timecode_scale)

            rest = text - events.keys()
            if rest:
                logger.info(f"No subtitle cues for tracks {sorted(rest)}: reading the clusters")
                found, cues_found = await extract_via_cues(reader, header, rest, timecode_scale)
                if not cues_found:
                    found = await extract_via_scan(reader, 0, rest, timecode_scale)
                for n in rest:
                    events[n] = [e for e in found if e.track == n]

    return [(t, events.get(t.track_number)) for t in tracks]
