"""FFprobe service for extracting media stream metadata."""

import asyncio
import json
import subprocess
from dataclasses import dataclass

from loguru import logger

from app.models.media import CodecType


def find_closest_keyframe(keyframes: list[float], target: float) -> float:
    """
    Find the closest keyframe at or before the target timestamp.

    Uses binary search for efficiency.

    Args:
        keyframes: Sorted list of keyframe timestamps
        target: Target timestamp in seconds

    Returns:
        Closest keyframe timestamp <= target, or 0 if none found
    """
    if not keyframes:
        return 0.0

    # Binary search for the largest keyframe <= target
    left, right = 0, len(keyframes) - 1
    result = 0.0

    while left <= right:
        mid = (left + right) // 2
        if keyframes[mid] <= target:
            result = keyframes[mid]
            left = mid + 1
        else:
            right = mid - 1

    return result


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
                        logger.debug(f"Downloaded {bytes_written // (1024*1024)}MB")

            logger.debug(f"Download complete: {bytes_written // (1024*1024)}MB")

            result = await self.probe_file(temp_path)
            return result

        except Exception as e:
            logger.error(f"Failed to analyze Telegram file: {e}")
            return None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)


    async def extract_keyframes(self, file_path: str, max_keyframes: int = 1000) -> list[float]:
        """
        Extract video keyframe timestamps using ffprobe.

        Uses packet analysis to find I-frames (keyframes) efficiently.
        Limited to max_keyframes to avoid huge lists for long videos.

        Args:
            file_path: Path or URL to the media file
            max_keyframes: Maximum number of keyframes to extract

        Returns:
            List of keyframe timestamps in seconds (sorted)
        """
        cmd = [
            self._ffprobe_cmd,
            "-v", "quiet",
            "-select_streams", "v:0",  # First video stream
            "-show_entries", "packet=pts_time,flags",
            "-of", "csv=print_section=0",
            file_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for large files
            )

            if result.returncode != 0:
                logger.error(f"ffprobe keyframes failed: {result.stderr}")
                return []

            keyframes: list[float] = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) >= 2:
                    pts_time, flags = parts[0], parts[1]
                    # 'K' flag indicates keyframe
                    if "K" in flags and pts_time:
                        try:
                            keyframes.append(float(pts_time))
                        except ValueError:
                            continue
                        if len(keyframes) >= max_keyframes:
                            break

            keyframes.sort()
            logger.debug(f"Extracted {len(keyframes)} keyframes")
            return keyframes

        except subprocess.TimeoutExpired:
            logger.error(f"ffprobe keyframes timeout for: {file_path}")
            return []
        except Exception as e:
            logger.error(f"ffprobe keyframes error: {e}")
            return []

    async def extract_keyframes_from_url(self, url: str, max_keyframes: int = 1000) -> list[float]:
        """
        Extract keyframes from a streaming URL.

        Note: This may be slow for remote URLs as ffprobe needs to read the full file.
        Consider using this only during ingest/scan.
        """
        return await self.extract_keyframes(url, max_keyframes)

    async def find_keyframe_at_time(self, file_path: str, target_time: float) -> float:
        """
        Find the closest keyframe at or before target_time using ffprobe.

        Uses -read_intervals to only read a small portion of the file,
        making this fast even for remote URLs.

        Args:
            file_path: Path or URL to the media file
            target_time: Target timestamp in seconds

        Returns:
            Keyframe timestamp in seconds (or target_time if not found)
        """
        # Read interval: from 10 seconds before target to target
        # This should contain the keyframe FFmpeg will seek to
        start = max(0, target_time - 10)
        interval = f"{start}%+15"  # Read 15 seconds starting from 'start'

        cmd = [
            self._ffprobe_cmd,
            "-v", "quiet",
            "-read_intervals", interval,
            "-select_streams", "v:0",
            "-show_entries", "packet=pts_time,flags",
            "-of", "csv=print_section=0",
            file_path,
        ]

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                # 90s timeout to handle Telegram FloodWait
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            )

            if result.returncode != 0:
                logger.warning(f"ffprobe find_keyframe failed: {result.stderr}")
                return target_time

            # Find the largest keyframe <= target_time
            best_keyframe = 0.0
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) >= 2:
                    pts_time_str, flags = parts[0], parts[1]
                    if "K" in flags and pts_time_str:
                        try:
                            pts_time = float(pts_time_str)
                            if pts_time <= target_time and pts_time > best_keyframe:
                                best_keyframe = pts_time
                        except ValueError:
                            continue

            if best_keyframe > 0:
                logger.debug(f"Found keyframe at {best_keyframe:.2f}s for target {target_time:.1f}s")
                return best_keyframe

            logger.warning(f"No keyframe found before {target_time}s, using target")
            return target_time

        except subprocess.TimeoutExpired:
            logger.error(f"ffprobe find_keyframe timeout for: {file_path}")
            return target_time
        except Exception as e:
            logger.error(f"ffprobe find_keyframe error: {e}")
            return target_time


# Global instance
ffprobe_service = FFProbeService()
