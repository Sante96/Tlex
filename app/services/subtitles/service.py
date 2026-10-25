"""Subtitle extraction service."""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from app.core.utils import find_mkvextract, find_mkvmerge
from app.services.subtitles.fonts import extract_font_names
from app.services.subtitles.models import AttachedFont

if TYPE_CHECKING:
    from app.services.streaming import VirtualStreamReader


def safe_font_filename(name: str | None, att_id: object) -> str:
    """Attachment names come from inside the MKV: keep only the base name, so a
    crafted "../../x" can't make mkvextract or the font cache write outside their dir."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    return base if base not in ("", ".", "..") else f"font_{att_id}.ttf"


class SubtitleExtractor:
    """
    Extracts attached fonts from MKV files (mkvmerge/mkvextract on the header only).

    Subtitle tracks themselves are parsed directly from the MKV by mkv_extractor.
    """

    def __init__(self) -> None:
        self._mkvextract_path = find_mkvextract()
        self._mkvmerge_path = find_mkvmerge()

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
            att
            for att in attachments
            if any(ext in att.get("file_name", "").lower() for ext in [".ttf", ".otf", ".woff"])
        ]

        if not font_attachments:
            logger.debug("No font attachments found")
            return []

        # Extract fonts with mkvextract
        extract_cmd = [self._mkvextract_path, str(header_file), "attachments"]

        for att in font_attachments:
            att_id = att.get("id")
            filename = safe_font_filename(att.get("file_name"), att_id)
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
            filename = safe_font_filename(att.get("file_name"), att_id)
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


subtitle_extractor = SubtitleExtractor()
