"""Font extraction logic."""

from io import BytesIO

from fontTools.ttLib import TTFont
from loguru import logger


def extract_font_names(font_data: bytes) -> list[str]:
    """Extract internal font names from TTF/OTF font data."""
    names: list[str] = []
    try:
        font = TTFont(BytesIO(font_data))
        name_table = font.get("name")

        if name_table:
            # Name IDs: 1=Family, 4=Full Name, 6=PostScript Name
            for name_id in [4, 1, 6]:
                for record in name_table.names:
                    if record.nameID == name_id:
                        try:
                            decoded = record.toUnicode()
                            if decoded and decoded not in names:
                                names.append(decoded)
                        except Exception:
                            pass
        font.close()
    except Exception as e:
        logger.debug(f"Could not extract font names: {e}")

    return names
