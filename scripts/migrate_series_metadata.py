"""Migration script to add genres, vote_average, content_rating to series table."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, async_session_maker
from app.services.tmdb import tmdb_client


async def add_columns() -> None:
    """Add new columns to series table if they don't exist."""
    async with engine.begin() as conn:
        # Check and add columns one by one (SQLite doesn't support IF NOT EXISTS for columns)
        try:
            await conn.execute(text("ALTER TABLE series ADD COLUMN genres TEXT"))
            print("✓ Added 'genres' column")
        except Exception:
            print("- 'genres' column already exists")

        try:
            await conn.execute(text("ALTER TABLE series ADD COLUMN vote_average REAL"))
            print("✓ Added 'vote_average' column")
        except Exception:
            print("- 'vote_average' column already exists")

        try:
            await conn.execute(text("ALTER TABLE series ADD COLUMN content_rating VARCHAR(20)"))
            print("✓ Added 'content_rating' column")
        except Exception:
            print("- 'content_rating' column already exists")


async def populate_metadata() -> None:
    """Fetch and populate metadata from TMDB for existing series."""
    async with async_session_maker() as session:
        # Get all series with tmdb_id
        result = await session.execute(
            text("SELECT id, tmdb_id, title FROM series WHERE tmdb_id IS NOT NULL")
        )
        series_list = result.fetchall()

        print(f"\nPopulating metadata for {len(series_list)} series...")

        for series_id, tmdb_id, title in series_list:
            try:
                details = await tmdb_client.get_tv_details(tmdb_id)
                if details:
                    genres_str = ",".join(details.genres) if details.genres else None
                    await session.execute(
                        text("""
                            UPDATE series 
                            SET genres = :genres,
                                vote_average = :vote_average,
                                content_rating = :content_rating
                            WHERE id = :id
                        """),
                        {
                            "id": series_id,
                            "genres": genres_str,
                            "vote_average": details.vote_average,
                            "content_rating": details.content_rating,
                        }
                    )
                    print(f"✓ {title}: {details.genres}, {details.vote_average}, {details.content_rating}")
                else:
                    print(f"✗ {title}: No TMDB data found")
            except Exception as e:
                print(f"✗ {title}: Error - {e}")

        await session.commit()
        print("\n✓ Migration complete!")


async def main() -> None:
    """Run migration."""
    print("=== Series Metadata Migration ===\n")
    await add_columns()
    await populate_metadata()


if __name__ == "__main__":
    asyncio.run(main())
