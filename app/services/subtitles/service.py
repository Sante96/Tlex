"""Subtitle extraction service."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from app.core.utils import find_ffmpeg, find_ffprobe, find_mkvextract, find_mkvmerge
from app.services.subtitles.fonts import extract_font_names
from app.services.subtitles.models import AttachedFont

if TYPE_CHECKING:
    from app.services.streaming import VirtualStreamReader


class SubtitleExtractor:
    """
    Extracts subtitles and fonts from media files using FFmpeg.

    This service handles:
    - Extraction of subtitle tracks (ASS, SRT) from media files.
    - Conversion of SRT subtitles to ASS format for consistent rendering.
    - Extraction of attached fonts from MKV files (using header sniping for performance).
    """

    def __init__(self) -> None:
        self._ffmpeg_path = find_ffmpeg()
        self._ffprobe_path = find_ffprobe()
        self._mkvextract_path = find_mkvextract()
        self._mkvmerge_path = find_mkvmerge()

    async def extract_subtitle_from_reader(
        self,
        reader: VirtualStreamReader,
        stream_index: int,
        output_format: str = "ass",
    ) -> bytes:
        """
        Extract a subtitle track directly from a VirtualStreamReader.

        This method downloads the file to a temp location and runs FFmpeg on it.
        FFmpeg needs seekable input for MKV containers, so piping doesn't work reliably.

        Args:
            reader: The VirtualStreamReader instance to read from.
            stream_index: The index of the subtitle stream to extract.
            output_format: The desired output format (default: "ass").

        Returns:
            The extracted subtitle content as bytes.

        Raises:
            RuntimeError: If FFmpeg execution fails.
        """
        # Read ENTIRE file - MKV subtitles are distributed throughout the file
        read_size = reader.total_size

        logger.debug(f"Reading {read_size / 1024 / 1024:.1f}MB for subtitle extraction")

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as tmp:
            tmp_path = tmp.name
            bytes_written = 0
            async for chunk in reader.read_range(0, read_size):
                tmp.write(chunk)
                bytes_written += len(chunk)

        logger.debug(f"Wrote {bytes_written / 1024 / 1024:.1f}MB to temp file")

        cmd = [
            self._ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-i", tmp_path,
            "-map", f"0:s:{stream_index}",
            "-c:s", output_format,
            "-f", output_format,
            "-",
        ]

        logger.debug(f"Extracting subtitle stream {stream_index} as {output_format}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        # Use subprocess.run in thread
        def run_ffmpeg():
            return subprocess.run(
                cmd,
                capture_output=True,
                timeout=120,  # Increased timeout for large files
            )

        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, run_ffmpeg)

            logger.debug(f"FFmpeg: code={result.returncode}, output={len(result.stdout)} bytes")
            if result.stderr:
                logger.warning(f"FFmpeg stderr: {result.stderr.decode()}")

            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                logger.error(f"Subtitle extraction failed (code {result.returncode}): {error_msg}")
                raise RuntimeError(error_msg or f"FFmpeg failed with code {result.returncode}")

            logger.debug(f"Extracted {len(result.stdout)} bytes subtitle")
            return result.stdout

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out")
            raise RuntimeError("Subtitle extraction timed out") from None

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def extract_all_fonts_from_reader(
        self, reader: VirtualStreamReader
    ) -> list[AttachedFont]:
        """
        Extract all attached fonts from an MKV file using VirtualStreamReader.

        This method optimizes performance by only reading the first 30MB of the file
        (where attachments usually reside in MKV headers) directly from the reader,
        bypassing the need for a full download or HTTP self-request.

        Args:
            reader: The VirtualStreamReader instance for the media.

        Returns:
            A list of AttachedFont objects found in the file header.
        """
        # Header Snipe: Download only first 5MB (attachments are in MKV header)
        HEADER_SIZE = 5 * 1024 * 1024  # 5MB

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            header_file = tmp_path / "header.mkv"

            # Read header directly from VirtualStreamReader
            try:
                chunks = []
                async for chunk in reader.read_range(0, HEADER_SIZE):
                    chunks.append(chunk)
                header_data = b"".join(chunks)
                header_file.write_bytes(header_data)
                logger.debug(f"Read {len(header_data)} bytes directly for header snipe")
            except Exception as e:
                logger.warning(f"Header read failed: {type(e).__name__}: {e}")
                return []

            return await self._extract_fonts_from_header(header_file, tmp_path)

    async def _extract_fonts_from_header(
        self, header_file: Path, tmp_path: Path
    ) -> list[AttachedFont]:
        """Common logic to extract fonts from a downloaded MKV header file."""
        # Analyze with mkvmerge -J
        probe_cmd = [self._mkvmerge_path, "-J", str(header_file)]

        def run_probe():
            return subprocess.run(probe_cmd, capture_output=True, timeout=10)

        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, run_probe)
        except Exception as e:
            logger.warning(f"MKV probe failed: {e}")
            return []

        # mkvmerge returns non-zero for truncated files but still outputs JSON
        try:
            data = json.loads(result.stdout.decode())
            attachments = data.get("attachments", [])
        except json.JSONDecodeError:
            logger.debug("No valid JSON from mkvmerge")
            return []

        if not attachments:
            logger.debug("No attachments found in MKV header")
            return []

        # Filter font attachments
        font_attachments = [
            att for att in attachments
            if any(ext in att.get("file_name", "").lower() for ext in [".ttf", ".otf", ".woff"])
        ]

        if not font_attachments:
            logger.debug("No font attachments found")
            return []

        # Extract fonts with mkvextract
        extract_cmd = [self._mkvextract_path, str(header_file), "attachments"]

        for att in font_attachments:
            att_id = att.get("id")
            filename = att.get("file_name", f"font_{att_id}.ttf")
            extract_cmd.append(f"{att_id}:{tmp_path / filename}")

        def run_extract():
            return subprocess.run(extract_cmd, capture_output=True, timeout=10)

        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                # check=False - ignore errors as file is truncated
                await loop.run_in_executor(executor, run_extract)
        except Exception as e:
            logger.warning(f"Font extraction failed: {e}")
            return []

        # Read extracted fonts and extract internal names
        fonts: list[AttachedFont] = []
        for att in font_attachments:
            att_id = att.get("id")
            filename = att.get("file_name", f"font_{att_id}.ttf")
            content_type = att.get("content_type", "application/x-font-ttf")
            font_path = tmp_path / filename

            if font_path.exists():
                font_data = font_path.read_bytes()
                font_names = extract_font_names(font_data)
                fonts.append(
                    AttachedFont(
                        filename=filename,
                        mimetype=content_type,
                        data=font_data,
                        font_names=font_names,
                    )
                )
                logger.debug(f"Extracted font: {filename} -> names: {font_names}")

        logger.info(f"Extracted {len(fonts)} fonts via header snipe")
        return fonts

    async def convert_srt_to_ass(self, srt_content: bytes) -> bytes:
        """
        Convert SRT subtitle to ASS format.

        Args:
            srt_content: SRT content as bytes

        Returns:
            ASS content as bytes
        """
        cmd = [
            self._ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "srt",
            "-i",
            "pipe:0",
            "-c:s",
            "ass",
            "-f",
            "ass",
            "-",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(input=srt_content)

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"SRT to ASS conversion failed: {error_msg}")

        return stdout


subtitle_extractor = SubtitleExtractor()
