"""Migration script to create backup_channels and backup_messages tables."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.database import engine


async def migrate() -> None:
    """Create backup tables and add all required columns."""
    async with engine.begin() as conn:
        # Create backup_channels table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS backup_channels (
                id SERIAL PRIMARY KEY,
                main_channel_id BIGINT NOT NULL,
                backup_channel_id BIGINT NOT NULL UNIQUE,
                title VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                synced_count INTEGER NOT NULL DEFAULT 0,
                topic_map JSONB,
                failure_count INTEGER NOT NULL DEFAULT 0,
                max_failures INTEGER NOT NULL DEFAULT 5,
                last_failure_at TIMESTAMP,
                is_promoted BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                last_sync_at TIMESTAMP
            )
        """))
        print("✅ Created backup_channels table")

        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_backup_channels_main_channel_id "
            "ON backup_channels(main_channel_id)"
        ))
        print("✅ Created index on backup_channels.main_channel_id")

        # Create backup_messages table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS backup_messages (
                id SERIAL PRIMARY KEY,
                backup_channel_db_id INTEGER NOT NULL
                    REFERENCES backup_channels(id) ON DELETE CASCADE,
                main_channel_id BIGINT NOT NULL,
                main_message_id INTEGER NOT NULL,
                backup_message_id INTEGER NOT NULL,
                synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_backup_msg UNIQUE (backup_channel_db_id, main_message_id)
            )
        """))
        print("✅ Created backup_messages table")

        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_backup_messages_main "
            "ON backup_messages(main_channel_id, main_message_id)"
        ))
        print("✅ Created index on backup_messages")

        # Add missing columns to existing tables (idempotent)
        new_columns = [
            ("topic_map",       "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS topic_map JSONB"),
            ("failure_count",   "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS failure_count INTEGER NOT NULL DEFAULT 0"),
            ("max_failures",    "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS max_failures INTEGER NOT NULL DEFAULT 5"),
            ("last_failure_at", "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS last_failure_at TIMESTAMP"),
            ("is_promoted",     "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS is_promoted BOOLEAN NOT NULL DEFAULT FALSE"),
        ]
        for col_name, sql in new_columns:
            await conn.execute(text(sql))
            print(f"✅ Column backup_channels.{col_name} ensured")

    print("\n✅ Backup migration complete")


if __name__ == "__main__":
    asyncio.run(migrate())
