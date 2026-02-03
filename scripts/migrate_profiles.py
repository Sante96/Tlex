"""Migration script to add worker_id and is_kids columns to profiles table."""

import asyncio

from sqlalchemy import text

from app.database import engine


async def migrate():
    """Add new columns to profiles table if they don't exist."""
    async with engine.begin() as conn:
        # Check and add worker_id column
        result = await conn.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'profiles' AND column_name = 'worker_id'
            """)
        )
        if not result.fetchone():
            print("Adding worker_id column...")
            await conn.execute(
                text("""
                    ALTER TABLE profiles 
                    ADD COLUMN worker_id INTEGER REFERENCES workers(id) ON DELETE SET NULL
                """)
            )
            print("✅ worker_id column added")
        else:
            print("ℹ️ worker_id column already exists")

        # Check and add is_kids column
        result = await conn.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'profiles' AND column_name = 'is_kids'
            """)
        )
        if not result.fetchone():
            print("Adding is_kids column...")
            await conn.execute(
                text("""
                    ALTER TABLE profiles 
                    ADD COLUMN is_kids BOOLEAN NOT NULL DEFAULT FALSE
                """)
            )
            print("✅ is_kids column added")
        else:
            print("ℹ️ is_kids column already exists")

        # Add unique constraint on worker_id if not exists
        result = await conn.execute(
            text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'profiles' AND constraint_name = 'uq_profile_worker'
            """)
        )
        if not result.fetchone():
            print("Adding unique constraint on worker_id...")
            await conn.execute(
                text("""
                    ALTER TABLE profiles 
                    ADD CONSTRAINT uq_profile_worker UNIQUE (worker_id)
                """)
            )
            print("✅ Unique constraint added")
        else:
            print("ℹ️ Unique constraint already exists")

    print("\n🎉 Migration completed!")


if __name__ == "__main__":
    asyncio.run(migrate())
