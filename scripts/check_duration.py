"""Check duration in database."""
import asyncio
import sys
sys.path.insert(0, ".")

from sqlalchemy import select
from app.database import async_session_maker
from app.models.media import MediaItem

async def main():
    async with async_session_maker() as session:
        result = await session.execute(select(MediaItem))
        items = result.scalars().all()
        for item in items:
            print(f"ID: {item.id}, Title: {item.title}, Duration: {item.duration_seconds}")

if __name__ == "__main__":
    asyncio.run(main())
