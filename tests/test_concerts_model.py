"""Concerts: a franchise (the anime/game page) and its concert media items."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.database import SCHEMA_UPGRADES
from app.models import Franchise
from app.models.media import MediaItem, MediaType


async def test_concert_belongs_to_franchise(test_session: AsyncSession):
    franchise = Franchise(key="arknights", title="Arknights")
    concert = MediaItem(
        title="Ambience Synesthesia 2024",
        media_type=MediaType.CONCERT,
        franchise=franchise,
        setlist=["Opening", None],
    )
    test_session.add(concert)
    await test_session.commit()

    row = (
        await test_session.execute(
            select(MediaItem).options(
                undefer(MediaItem.setlist), selectinload(MediaItem.franchise)
            )
        )
    ).scalar_one()
    assert row.franchise is not None
    assert row.franchise.title == "Arknights"
    assert row.setlist == ["Opening", None]
    assert row.series_id is None


def test_schema_upgrades_bring_concerts_to_existing_databases():
    assert "ALTER TYPE mediatype ADD VALUE IF NOT EXISTS 'CONCERT'" in SCHEMA_UPGRADES
    assert (
        "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS franchise_id INTEGER "
        "REFERENCES franchises(id) ON DELETE SET NULL"
    ) in SCHEMA_UPGRADES
    assert "ALTER TABLE media_items ADD COLUMN IF NOT EXISTS setlist JSON" in SCHEMA_UPGRADES
    assert (
        "CREATE INDEX IF NOT EXISTS ix_media_items_franchise_id ON media_items (franchise_id)"
    ) in SCHEMA_UPGRADES
