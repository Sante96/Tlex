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

import httpx
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

    async def extract_subtitle(
        self,
        input_url: str,
        stream_index: int,
        output_format: str = "ass",
    ) -> bytes:
        """
        Extract a subtitle track from media via URL.

        DEPRECATED: Use extract_subtitle_from_reader to avoid HTTP conflicts.

        Args:
            input_url: URL to media stream
            stream_index: Subtitle stream index
            output_format: Output format (ass, srt)

        Returns:
            Subtitle content as bytes
        """
        cmd = [
            self._ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-analyzeduration", "100M",
            "-probesize", "100M",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i",
            input_url,
            "-map",
            f"0:s:{stream_index}",
            "-c:s",
            output_format,
            "-f",
            output_format,
            "-",
        ]

        logger.debug(f"Extracting subtitle: stream {stream_index} as {output_format}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        def run_ffmpeg():
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=300,
            )
            return result

        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, run_ffmpeg)
        except Exception as e:
            logger.error(f"FFmpeg execution error: {e}")
            raise RuntimeError(f"FFmpeg execution failed: {e}") from e

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "Unknown error"
            logger.error(f"Subtitle extraction failed (code {result.returncode}): {error_msg}")
            raise RuntimeError(error_msg or f"FFmpeg failed with code {result.returncode}")

        stdout = result.stdout
        logger.info(f"Extracted subtitle: {len(stdout)} bytes")
        return stdout

    async def extract_subtitle_from_reader(
        self,
        reader: VirtualStreamReader,
        stream_index: int,
        output_format: str = "ass",
    ) -> bytes:
        """
        Extract a subtitle track directly from a VirtualStreamReader.

        This method reads the full file content from the virtual reader and processes it
        with FFmpeg. This avoids HTTP conflicts and allows extracting subtitles from
        files that are split across multiple parts.

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

        logger.info(f"Reading {read_size / 1024 / 1024:.1f}MB for subtitle extraction (full file)")

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as tmp:
            tmp_path = tmp.name
            bytes_written = 0
            async for chunk in reader.read_range(0, read_size):
                tmp.write(chunk)
                bytes_written += len(chunk)

        logger.info(f"Wrote {bytes_written} bytes to temp file: {tmp_path}")

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

        logger.info(f"Extracting subtitle from temp file: stream {stream_index} as {output_format}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        # Use subprocess.run in thread
        def run_ffmpeg():
            return subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
            )

        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, run_ffmpeg)

            logger.info(f"FFmpeg finished: returncode={result.returncode}, stdout={len(result.stdout)} bytes")
            if result.stderr:
                logger.warning(f"FFmpeg stderr: {result.stderr.decode()}")

            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                logger.error(f"Subtitle extraction failed (code {result.returncode}): {error_msg}")
                raise RuntimeError(error_msg or f"FFmpeg failed with code {result.returncode}")

            logger.info(f"Extracted subtitle from reader: {len(result.stdout)} bytes")
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
        # Header Snipe: Download only first 30MB (attachments are in MKV header)
        HEADER_SIZE = 30 * 1024 * 1024  # 30MB

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

    async def extract_all_fonts(self, input_url: str) -> list[AttachedFont]:
        """
        Extract all attached fonts from MKV container using "Header Snipe" technique.

        DEPRECATED: Use extract_all_fonts_from_reader for better performance.

        Downloads only the first 30MB of the file (where attachments live in MKV header)
        and uses mkvextract on that truncated file. Much faster than downloading entire file.

        Args:
            input_url: URL to media stream

        Returns:
            List of AttachedFont objects
        """
        # Header Snipe: Download only first 30MB (attachments are in MKV header)
        HEADER_SIZE = 30 * 1024 * 1024  # 30MB

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            header_file = tmp_path / "header.mkv"

            # Download only the header portion using Range request
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    headers = {"Range": f"bytes=0-{HEADER_SIZE - 1}"}
                    response = await client.get(input_url, headers=headers)

                    if response.status_code not in (200, 206):
                        logger.warning(f"Failed to download header: {response.status_code}")
                        return []

                    header_file.write_bytes(response.content)
                    logger.debug(f"Downloaded {len(response.content)} bytes for header snipe")
            except Exception as e:
                logger.warning(f"Header download failed: {type(e).__name__}: {e}")
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
