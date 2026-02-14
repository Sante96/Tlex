"""Script to add a new Telegram worker account."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


from app.config import get_settings  # noqa: E402
from app.database import async_session_maker, engine  # noqa: E402
from app.models.worker import Worker, WorkerStatus  # noqa: E402

settings = get_settings()


async def main() -> None:
    """Interactive CLI to add a new worker account."""
    print("=" * 50)
    print("  TLEX - Add Telegram Worker Account")
    print("=" * 50)
    print()

    # Get phone number
    phone = input("Enter phone number (with country code, e.g., +39123456789): ").strip()
    if not phone:
        print("❌ Phone number is required")
        return

    print()
    print("Starting Telegram authentication...")
    print("You will receive a code on Telegram.")
    print()

    # Create client and login
    from pyrogram import Client
    
    client = Client(
        name="new_worker",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        phone_number=phone,
        in_memory=True,
    )

    try:
        await client.start()

        # Get session string
        session_string = await client.export_session_string()

        # Check if premium
        me = await client.get_me()
        is_premium = me.is_premium or False

        print()
        print(f"✅ Logged in as: {me.first_name} (@{me.username})")
        print(f"   Premium: {'Yes ⭐' if is_premium else 'No'}")
        print()

        # Save to database
        async with async_session_maker() as session:
            # Check if worker already exists
            from sqlalchemy import select

            stmt = select(Worker).where(Worker.phone_number == phone)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                print("⚠️  Worker with this phone number already exists!")
                update = input("Update existing worker? (y/N): ").strip().lower()
                if update == "y":
                    existing.session_string = session_string
                    existing.is_premium = is_premium
                    existing.max_concurrent_streams = 10 if is_premium else 1
                    existing.status = WorkerStatus.ACTIVE
                    await session.commit()
                    print("✅ Worker updated!")
                else:
                    print("Cancelled.")
                    return
            else:
                worker = Worker(
                    session_string=session_string,
                    phone_number=phone,
                    is_premium=is_premium,
                    max_concurrent_streams=10 if is_premium else 1,
                    status=WorkerStatus.ACTIVE,
                )
                session.add(worker)
                await session.commit()
                print(f"✅ Worker added with ID: {worker.id}")

        print()
        print("Worker is ready to use!")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        await client.stop()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
