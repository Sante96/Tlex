"""Migration script to add extra_sessions column to workers table."""

import asyncio

from sqlalchemy import text

from app.database import async_session_maker


async def migrate():
    """Add extra_sessions column to workers table if it doesn't exist."""
    async with async_session_maker() as session:
        # Check if column exists
        result = await session.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'workers' AND column_name = 'extra_sessions'
            """)
        )
        exists = result.scalar_one_or_none()

        if exists:
            print("Column 'extra_sessions' already exists. Skipping migration.")
            return

        # Add column
        await session.execute(
            text("ALTER TABLE workers ADD COLUMN extra_sessions JSON DEFAULT NULL")
        )
        await session.commit()
        print("Successfully added 'extra_sessions' column to workers table.")


if __name__ == "__main__":
    asyncio.run(migrate())
