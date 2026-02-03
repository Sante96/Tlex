"""Migration script to create watchlist table."""

import asyncio

from sqlalchemy import text

from app.database import engine


async def migrate():
    """Create watchlist table if not exists."""
    async with engine.begin() as conn:
        # Create table
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    media_item_id INTEGER NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    CONSTRAINT uq_watchlist_user_media UNIQUE (user_id, media_item_id)
                )
            """)
        )
        print("✅ Created watchlist table")
        
        # Create index
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_watchlist_user_id ON watchlist(user_id)")
        )
        print("✅ Created index")


if __name__ == "__main__":
    asyncio.run(migrate())
