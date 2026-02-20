"""Add content_rating, vote_average, genres columns to media_items table."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.database import engine

COLUMNS = [
    ("content_rating", "VARCHAR(20)"),
    ("vote_average", "FLOAT"),
    ("genres", "TEXT"),
]


async def migrate() -> None:
    async with engine.begin() as conn:
        for col_name, col_type in COLUMNS:
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = 'media_items' AND column_name = '{col_name}'"
            ))
            if result.fetchone():
                print(f"Column '{col_name}' already exists, skipping.")
            else:
                await conn.execute(text(
                    f"ALTER TABLE media_items ADD COLUMN {col_name} {col_type}"
                ))
                print(f"Added '{col_name}' column to media_items table.")


if __name__ == "__main__":
    asyncio.run(migrate())
