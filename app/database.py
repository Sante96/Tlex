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
    # PostgreSQL doesn't index foreign keys: every parts/streams/episodes load scanned
    # the whole table. Same names as the models' index=True, so new databases match.
    "CREATE INDEX IF NOT EXISTS ix_media_items_series_id ON media_items (series_id)",
    "CREATE INDEX IF NOT EXISTS ix_media_parts_media_item_id ON media_parts (media_item_id)",
    "CREATE INDEX IF NOT EXISTS ix_media_streams_media_item_id ON media_streams (media_item_id)",
    "CREATE INDEX IF NOT EXISTS ix_media_parts_channel_message ON media_parts (channel_id, message_id)",
    # Keyframe lists also held subtitle cue times: a new column starts them over
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS video_keyframes TEXT",
    "ALTER TABLE media_items DROP COLUMN IF EXISTS keyframes_index",
    "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ",
    # NULL until probed: the startup task reads the chapters of the titles already there
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS chapters JSON",
    # Concerts. The new enum value isn't used in this transaction (PostgreSQL forbids it);
    # create_all has made the franchises table before these run
    "ALTER TYPE mediatype ADD VALUE IF NOT EXISTS 'CONCERT'",
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS franchise_id INTEGER "
    "REFERENCES franchises(id) ON DELETE SET NULL",
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS setlist JSON",
    "CREATE INDEX IF NOT EXISTS ix_media_items_franchise_id ON media_items (franchise_id)",
    # Profiles keep their own watch progress and watchlist. Every user gets a profile if
    # they had none; rows from before go to the user's first profile. Uniqueness moves
    # from (user, media) to (profile, media): the old rule, re-run at every start, would
    # delete the other profiles' rows.
    "INSERT INTO profiles (user_id, name, is_kids, preferences)"
    " SELECT u.id, split_part(u.email, '@', 1), FALSE, '{}' FROM users u"
    " WHERE NOT EXISTS (SELECT 1 FROM profiles p WHERE p.user_id = u.id)",
    "ALTER TABLE watch_progress ADD COLUMN IF NOT EXISTS profile_id INTEGER"
    " REFERENCES profiles(id) ON DELETE CASCADE",
    "UPDATE watch_progress w SET profile_id = (SELECT min(p.id) FROM profiles p"
    " WHERE p.user_id = w.user_id) WHERE profile_id IS NULL",
    "ALTER TABLE watch_progress ALTER COLUMN profile_id SET NOT NULL",
    "DROP INDEX IF EXISTS uq_watch_progress_user_media",
    "DELETE FROM watch_progress a USING watch_progress b WHERE a.profile_id = b.profile_id"
    " AND a.media_item_id = b.media_item_id AND a.id < b.id",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_watch_progress_profile_media"
    " ON watch_progress (profile_id, media_item_id)",
    "ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS profile_id INTEGER"
    " REFERENCES profiles(id) ON DELETE CASCADE",
    "UPDATE watchlist w SET profile_id = (SELECT min(p.id) FROM profiles p"
    " WHERE p.user_id = w.user_id) WHERE profile_id IS NULL",
    "ALTER TABLE watchlist ALTER COLUMN profile_id SET NOT NULL",
    "ALTER TABLE watchlist DROP CONSTRAINT IF EXISTS uq_watchlist_user_media",
    "ALTER TABLE watchlist DROP CONSTRAINT IF EXISTS uq_watchlist_user_series",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_watchlist_profile_media"
    " ON watchlist (profile_id, media_item_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_watchlist_profile_series ON watchlist (profile_id, series_id)",
    # Archive groups (create_all has made archive_accounts before these run)
    "ALTER TABLE backup_channels ADD COLUMN IF NOT EXISTS archive_account_id INTEGER"
    " REFERENCES archive_accounts(id)",
    # Titles taken out of Continue Watching
    "ALTER TABLE watch_progress ADD COLUMN IF NOT EXISTS hidden BOOLEAN NOT NULL DEFAULT FALSE",
    # Where the credits start (Up next)
    "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS credits_start_seconds INTEGER",
)


async def create_all_tables() -> None:
    """Create missing tables, then bring existing ones up to date (PostgreSQL)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            for statement in SCHEMA_UPGRADES:
                await conn.execute(text(statement))
