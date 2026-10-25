"""SQLAlchemy async database setup."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Create async engine
# Note: echo=False to avoid noisy SQL logs (use echo="debug" for debugging)
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# create_all never alters a table that already exists. Columns and constraints added
# after a table first shipped go here, idempotent, so older databases catch up at startup.
SCHEMA_UPGRADES = (
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS extra_sessions JSON",
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS content_rating VARCHAR(20)",
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS vote_average FLOAT",
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS genres TEXT",
    "ALTER TABLE series ADD COLUMN IF NOT EXISTS genres TEXT",
    "ALTER TABLE series ADD COLUMN IF NOT EXISTS vote_average FLOAT",
    "ALTER TABLE series ADD COLUMN IF NOT EXISTS content_rating VARCHAR(20)",
    "ALTER TABLE series ADD COLUMN IF NOT EXISTS season_posters JSON",
    "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS worker_id INTEGER"
    " REFERENCES workers(id) ON DELETE SET NULL",
    "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_kids BOOLEAN NOT NULL DEFAULT FALSE",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_profile_worker ON profiles (worker_id)",
    "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS topic_map JSON",
    "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS failure_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS max_failures INTEGER NOT NULL DEFAULT 5",
    "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS last_failure_at TIMESTAMP",
    "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS is_promoted BOOLEAN NOT NULL DEFAULT FALSE",
    # watch_progress had no unique (user, media): keep the newest duplicate, then enforce it
    "DELETE FROM watch_progress a USING watch_progress b"
    " WHERE a.user_id = b.user_id AND a.media_item_id = b.media_item_id AND a.id < b.id",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_watch_progress_user_media"
    " ON watch_progress (user_id, media_item_id)",
    # PostgreSQL doesn't index foreign keys: every parts/streams/episodes load scanned
    # the whole table. Same names as the models' index=True, so new databases match.
    "CREATE INDEX IF NOT EXISTS ix_media_items_series_id ON media_items (series_id)",
    "CREATE INDEX IF NOT EXISTS ix_media_parts_media_item_id ON media_parts (media_item_id)",
    "CREATE INDEX IF NOT EXISTS ix_media_streams_media_item_id ON media_streams (media_item_id)",
    "CREATE INDEX IF NOT EXISTS ix_media_parts_channel_message ON media_parts (channel_id, message_id)",
    # Keyframe lists also held subtitle cue times: a new column starts them over
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS video_keyframes TEXT",
    "ALTER TABLE media_items DROP COLUMN IF EXISTS keyframes_index",
)


async def create_all_tables() -> None:
    """Create missing tables, then bring existing ones up to date (PostgreSQL)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            for statement in SCHEMA_UPGRADES:
                await conn.execute(text(statement))
