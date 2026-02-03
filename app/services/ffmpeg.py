"""FFmpeg remuxing pipeline for browser-compatible streaming."""

import asyncio
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread

from loguru import logger

from app.config import get_settings
from app.core.utils import find_ffmpeg

settings = get_settings()


@dataclass
class RemuxOptions:
    """Options for FFmpeg remuxing."""

    video_stream: int = 0  # Video stream index to use
    audio_stream: int = 0  # Audio stream index to use
    audio_codec: str = "aac"  # Target audio codec
    audio_bitrate: str = "192k"  # Audio bitrate
    start_time: float | None = None  # Seek position in seconds (for output trim)
    pre_seek_time: float | None = None  # Pre-seek position (before input, for faster load)


class FFmpegRemuxer:
    """
    FFmpeg-based remuxer for browser-compatible streaming.

    Features:
    - Zero video transcoding (copy)
    - Audio transcode to AAC (browser compatible)
    - Fragmented MP4 output for streaming
    - Pipe-based streaming (no temp files)
    """

    def __init__(self) -> None:
        self._ffmpeg_path = find_ffmpeg()

    def build_command(
        self,
        input_url: str,
        options: RemuxOptions,
    ) -> list[str]:
        """
        Build FFmpeg command for remuxing.

        Args:
            input_url: URL to input stream (our raw stream endpoint)
            options: Remuxing options

        Returns:
            Command as list of arguments
        """
        cmd = [
            self._ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-probesize", "1M",
            "-analyzeduration", "1M",
            "-seekable", "1",
        ]

        # Seek configuration: use pre_seek_time before input for fast demuxer seek
        # This seeks BEFORE the target keyframe to give network time to deliver data
        pre_seek = options.pre_seek_time if options.pre_seek_time is not None else options.start_time
        if pre_seek is not None and pre_seek > 0:
            cmd.extend([
                "-ss", str(pre_seek),
            ])

        # HTTP input options
        cmd.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            # genpts: Generate PTS if missing (crucial for container formats)
            # discardcorrupt: Drop bad packets to prevent sync issues
            "-fflags", "+genpts+discardcorrupt",
            "-i",
            input_url,
        ])

        # Accurate seek AFTER input - this ensures A/V sync
        # Trim to the actual keyframe position (relative to pre_seek)
        if options.start_time is not None and options.start_time > 0:
            # Calculate offset from pre_seek to actual start
            trim_offset = options.start_time - (pre_seek if pre_seek else 0)
            if trim_offset > 0:
                cmd.extend([
                    "-ss", str(trim_offset),
                ])
            else:
                cmd.extend([
                    "-ss", "0",
                ])

        # Video: copy (no transcode)
        cmd.extend(
            [
                "-map",
                f"0:v:{options.video_stream}",
                "-c:v",
                "copy",
            ]
        )

        # Audio: transcode to AAC
        cmd.extend(
            [
                "-map",
                f"0:a:{options.audio_stream}",
                "-c:a",
                options.audio_codec,
                "-b:a",
                options.audio_bitrate,
            ]
        )

        # Output format: fragmented MP4 for streaming
        cmd.extend(
            [
                # Handle negative timestamps by shifting to zero
                "-avoid_negative_ts", "make_zero",
                "-max_interleave_delta", "0",
                "-movflags",
                "frag_keyframe+empty_moov+default_base_moof+faststart",
                "-flush_packets", "1",
                "-f",
                "mp4",
                "-",  # Output to stdout
            ]
        )

        return cmd

    async def stream(
        self,
        input_url: str,
        options: RemuxOptions | None = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream remuxed video.

        Uses synchronous subprocess in a thread for Windows compatibility.

        Args:
            input_url: URL to raw media stream
            options: Remuxing options

        Yields:
            Chunks of remuxed video data
        """
        if options is None:
            options = RemuxOptions()

        import time
        start_time = time.time()

        cmd = self.build_command(input_url, options)
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        chunk_size = 64 * 1024  # 64KB chunks
        queue: Queue[bytes | None] = Queue(maxsize=100)
        first_chunk_time = [None]  # Use list to allow mutation in nested function

        def reader_thread(proc: subprocess.Popen, q: Queue) -> None:
            """Read stdout in a separate thread."""
            try:
                chunk_count = 0
                while True:
                    chunk = proc.stdout.read(chunk_size)
                    if not chunk:
                        break
                    chunk_count += 1
                    if chunk_count == 1:
                        first_chunk_time[0] = time.time()
                        elapsed = first_chunk_time[0] - start_time
                        logger.debug(f"FFmpeg first chunk after {elapsed:.2f}s")
                    q.put(chunk)
                logger.debug(f"FFmpeg stream complete: {chunk_count} chunks")
            except Exception as e:
                logger.error(f"Reader thread error: {e}")
            finally:
                q.put(None)  # Signal end

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        thread = Thread(target=reader_thread, args=(process, queue), daemon=True)
        thread.start()

        try:
            while True:
                try:
                    chunk = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: queue.get(timeout=1.0)
                    )
                    if chunk is None:
                        break
                    yield chunk
                except Empty:
                    if process.poll() is not None:
                        break
                    continue

            process.wait()

            if process.returncode != 0:
                stderr = process.stderr.read()
                if stderr:
                    logger.error(f"FFmpeg error (code {process.returncode}): {stderr.decode()}")

        except asyncio.CancelledError:
            logger.info("Stream cancelled, terminating FFmpeg")
            process.terminate()
            process.wait()
            raise

        except Exception as e:
            logger.error(f"FFmpeg streaming error: {e}")
            process.terminate()
            process.wait()
            raise

        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()


# Global instance
ffmpeg_remuxer = FFmpegRemuxer()
