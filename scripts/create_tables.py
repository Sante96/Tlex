"""Script to create all database tables."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import create_all_tables, engine  # noqa: E402
from app.models import (  # noqa: E402, F401
    MediaItem,
    MediaPart,
    MediaStream,
    Profile,
    Series,
    User,
    Worker,
)


async def main() -> None:
    """Create all database tables."""
    print("Creating database tables...")

    try:
        await create_all_tables()
        print("✅ All tables created successfully!")
        print("\nTables created:")
        print("  - users")
        print("  - profiles")
        print("  - workers")
        print("  - series")
        print("  - media_items")
        print("  - media_parts")
        print("  - media_streams")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
