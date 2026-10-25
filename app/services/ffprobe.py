"""FFprobe service for extracting media stream metadata."""

import json
import subprocess
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
    bit_rate: int | None  # bits per second, for estimating multi-part duration
    streams: list[StreamInfo]
    keyframes: list[float] | None = None  # Keyframe timestamps in seconds


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
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
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

        # Extract duration and bitrate from format
        duration_seconds = None
        bit_rate = None

        if "format" in data:
            fmt = data["format"]
            if "duration" in fmt:
                try:
                    duration_seconds = int(float(fmt["duration"]))
                except (ValueError, TypeError):
                    pass
            if "bit_rate" in fmt:
                try:
                    bit_rate = int(fmt["bit_rate"])
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

        return ProbeResult(
            duration_seconds=duration_seconds,
            bit_rate=bit_rate,
            streams=streams,
            keyframes=None,  # Extracted separately for performance
        )

    async def analyze_from_telegram(
        self, client, file_id: str, suffix: str = ".mkv", max_mb: int = 50
    ) -> ProbeResult | None:
        """
        Analyze a Telegram file by streaming only the first chunks.

        MKV/MP4 metadata is in the header, so we only need the first few MB.

        Args:
            client: Pyrogram client
            file_id: Telegram file ID
            suffix: File suffix for temp file
            max_mb: Maximum MB to download (default 50MB for metadata)

        Returns:
            ProbeResult or None
        """
        import os
        import tempfile

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                temp_path = tmp.name

            logger.debug(f"Streaming first {max_mb}MB for analysis: {file_id[:20]}...")

            # Stream only first chunks (1 chunk = 1MB in Pyrogram)
            bytes_written = 0
            with open(temp_path, "wb") as f:
                async for chunk in client.stream_media(file_id, limit=max_mb):
                    f.write(chunk)
                    bytes_written += len(chunk)
                    if bytes_written % (10 * 1024 * 1024) == 0:
                        logger.debug(f"Downloaded {bytes_written // (1024 * 1024)}MB")

            logger.debug(f"Download complete: {bytes_written // (1024 * 1024)}MB")

            result = await self.probe_file(temp_path)
            return result

        except Exception as e:
            logger.error(f"Failed to analyze Telegram file: {e}")
            return None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)


# Global instance
ffprobe_service = FFProbeService()
