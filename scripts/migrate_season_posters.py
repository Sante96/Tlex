"""Add season_posters JSON column to series table."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import async_engine


async def migrate():
    async with async_engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'series' AND column_name = 'season_posters'"
        ))
        if result.fetchone():
            print("Column 'season_posters' already exists, skipping.")
            return

        await conn.execute(text(
            "ALTER TABLE series ADD COLUMN season_posters JSON"
        ))
        print("Added 'season_posters' column to series table.")


if __name__ == "__main__":
    asyncio.run(migrate())
