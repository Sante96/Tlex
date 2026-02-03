"""Migration script to create refresh_tokens table."""

import asyncio

from sqlalchemy import text

from app.database import engine


async def migrate():
    """Create refresh_tokens table if not exists."""
    async with engine.begin() as conn:
        # Create table
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token VARCHAR(500) NOT NULL UNIQUE,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    revoked BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
        )
        print("✅ Created refresh_tokens table")
        
        # Create indexes
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens(user_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token ON refresh_tokens(token)")
        )
        print("✅ Created indexes")


if __name__ == "__main__":
    asyncio.run(migrate())
