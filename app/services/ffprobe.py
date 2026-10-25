"""FFprobe service for extracting media stream metadata."""

import asyncio
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass

from loguru import logger

from app.models.media import CodecType


@dataclass
class StreamInfo:
    """Extracted stream information from ffprobe."""

    stream_index: int
    codec_type: CodecType
    codec_name: str
    language: str | None = None
    title: str | None = None
    is_default: bool = False


@dataclass
class ProbeResult:
    """Result of ffprobe analysis."""

    duration_seconds: int | None
    streams: list[StreamInfo]


class FFProbeService:
    """Service for analyzing media files with ffprobe."""

    def __init__(self) -> None:
        self._ffprobe_cmd = "ffprobe"

    def _map_codec_type(self, codec_type: str) -> CodecType | None:
        """Map ffprobe codec_type to our CodecType enum."""
        mapping = {
            "video": CodecType.VIDEO,
            "audio": CodecType.AUDIO,
            "subtitle": CodecType.SUBTITLE,
        }
        return mapping.get(codec_type.lower())

    async def probe_file(self, file_path: str) -> ProbeResult | None:
        """
        Analyze a media file and extract stream information.

        Args:
            file_path: Path or URL to the media file

        Returns:
            ProbeResult with duration and streams, or None on error
        """
        cmd = [
            self._ffprobe_cmd,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]

        try:
            # In a thread: a 60 s ffprobe must not freeze the event loop (and every stream)
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                logger.error(f"ffprobe failed: {result.stderr}")
                return None

            data = json.loads(result.stdout)
            return self._parse_probe_data(data)

        except subprocess.TimeoutExpired:
            logger.error(f"ffprobe timeout for: {file_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ffprobe output: {e}")
            return None
        except FileNotFoundError:
            logger.error("ffprobe not found. Please install FFmpeg.")
            return None
        except Exception as e:
            logger.error(f"ffprobe error: {e}")
            return None

    def _parse_probe_data(self, data: dict) -> ProbeResult:
        """Parse ffprobe JSON output into ProbeResult."""
        streams: list[StreamInfo] = []

        duration_seconds = None
        if "duration" in data.get("format", {}):
            try:
                duration_seconds = int(float(data["format"]["duration"]))
            except (ValueError, TypeError):
                pass

        # Extract streams
        for stream in data.get("streams", []):
            codec_type = self._map_codec_type(stream.get("codec_type", ""))
            if codec_type is None:
                continue

            # Get language from tags
            tags = stream.get("tags", {})
            language = tags.get("language")
            title = tags.get("title")

            # Check if default
            disposition = stream.get("disposition", {})
            is_default = disposition.get("default", 0) == 1

            stream_info = StreamInfo(
                stream_index=stream.get("index", 0),
                codec_type=codec_type,
                codec_name=stream.get("codec_name", "unknown"),
                language=language,
                title=title,
                is_default=is_default,
            )
            streams.append(stream_info)

        return ProbeResult(duration_seconds=duration_seconds, streams=streams)

    async def analyze_from_telegram(
        self, client, file_id: str, suffix: str = ".mkv"
    ) -> ProbeResult | None:
        """
        Analyze a Telegram file from its first chunks only.

        An MKV keeps its tracks and duration in the first KBs: probe the first 4 MB, and
        keep downloading up to 50 MB only when that wasn't enough (a header pushed back by
        big attachments, say). A scan used to pull 50 MB for every new file.
        """
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                temp_path = tmp.name
            result = None
            downloaded = 0  # 1 MB chunks
            for upto in (4, 50):
                with open(temp_path, "ab") as f:
                    async for chunk in client.stream_media(
                        file_id, offset=downloaded, limit=upto - downloaded
                    ):
                        f.write(chunk)
                downloaded = upto
                result = await self.probe_file(temp_path)
                if result and result.streams and result.duration_seconds:
                    break
                logger.debug(f"Probe needs more than {upto} MB of {file_id[:20]}...")
            return result

        except Exception as e:
            logger.error(f"Failed to analyze Telegram file: {e}")
            return None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)


# Global instance
ffprobe_service = FFProbeService()
