"""Script to make a user admin."""

import asyncio
import sys

from sqlalchemy import select, update

from app.database import async_session_maker
from app.models.user import User


async def make_admin(email: str):
    """Make a user admin by email."""
    async with async_session_maker() as session:
        # Find user
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            print(f"❌ User with email '{email}' not found")
            return False

        if user.is_admin:
            print(f"ℹ️ User '{email}' is already admin")
            return True

        # Make admin
        await session.execute(
            update(User).where(User.id == user.id).values(is_admin=True)
        )
        await session.commit()
        print(f"✅ User '{email}' is now admin")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/make_admin.py <email>")
        sys.exit(1)

    email = sys.argv[1]
    asyncio.run(make_admin(email))
