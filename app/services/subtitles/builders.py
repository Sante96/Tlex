"""ASS and SRT subtitle content builders."""

from io import BytesIO

from app.services.subtitles.ebml_parser import MkvSubtitleTrack, SubtitleEvent


def _format_ass_time(ms: int) -> str:
    """Format milliseconds as ASS timestamp H:MM:SS.cc."""
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    cs = (ms % 1000) // 10
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _format_srt_time(ms: int) -> str:
    """Format milliseconds as SRT timestamp HH:MM:SS,mmm."""
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    sms = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{sms:03d}"


def _decode_text(data: bytes) -> str:
    """Decode subtitle text with fallback encoding."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def build_ass_content(track: MkvSubtitleTrack, events: list[SubtitleEvent]) -> bytes:
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
        # Strip null bytes — MKV containers sometimes pad CodecPrivate with trailing \x00
        header = track.codec_private.replace(b"\x00", b"")
        output.write(header)

        if not header.endswith(b"\n"):
            output.write(b"\n")

        # Add Events section if not present
        if b"[Events]" not in header:
            output.write(b"\n[Events]\n")
            output.write(
                b"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            )
    else:
        # Generate minimal ASS header
        output.write(b"[Script Info]\nScriptType: v4.00+\n\n")
        output.write(b"[V4+ Styles]\n")
        output.write(
            b"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            b"OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            b"ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            b"Alignment, MarginL, MarginR, MarginV, Encoding\n"
        )
        output.write(
            b"Style: Default,Arial,20,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,"
            b"0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n"
        )
        output.write(b"\n[Events]\n")
        output.write(
            b"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

    events.sort(key=lambda e: e.timestamp_ms)

    for event in events:
        start_str = _format_ass_time(event.timestamp_ms)
        end_str = _format_ass_time(event.timestamp_ms + (event.duration_ms or 5000))
        text = _decode_text(event.data)

        # For ASS format from MKV, data is:
        # ReadOrder,Layer,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        if "," in text and track.codec_id == "S_TEXT/ASS":
            parts = text.split(",", 8)
            if len(parts) >= 9:
                layer = parts[1]
                style = parts[2]
                name = parts[3]
                margin_l = parts[4]
                margin_r = parts[5]
                margin_v = parts[6]
                effect = parts[7]
                dialogue_text = parts[8]
                line = (
                    f"Dialogue: {layer},{start_str},{end_str},{style},{name},"
                    f"{margin_l},{margin_r},{margin_v},{effect},{dialogue_text}\n"
                )
            else:
                line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"
        else:
            line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"

        output.write(line.encode("utf-8"))

    return output.getvalue()


def build_srt_content(events: list[SubtitleEvent]) -> bytes:
    """Build SRT file content from events."""
    output = BytesIO()

    events.sort(key=lambda e: e.timestamp_ms)

    for i, event in enumerate(events, 1):
        output.write(f"{i}\n".encode())

        start_str = _format_srt_time(event.timestamp_ms)
        end_str = _format_srt_time(event.timestamp_ms + (event.duration_ms or 5000))
        output.write(f"{start_str} --> {end_str}\n".encode())

        text = _decode_text(event.data).strip()
        output.write(f"{text}\n\n".encode())

    return output.getvalue()
