import asyncio
import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from sqlalchemy import select, update

from app.database import async_session_maker
from app.models.worker import Worker, WorkerStatus


async def reset_workers():
    """Reset all OFFLINE workers to ACTIVE status."""
    async with async_session_maker() as session:
        # Find offline workers
        stmt = select(Worker).where(Worker.status == WorkerStatus.OFFLINE)
        result = await session.execute(stmt)
        workers = result.scalars().all()

        if not workers:
            print("No offline workers found.")
            return

        print(f"Found {len(workers)} offline workers. Resetting to ACTIVE...")

        for worker in workers:
            worker.status = WorkerStatus.ACTIVE
            print(f"  - Reset worker {worker.id} ({worker.phone_number})")

        await session.commit()
        print("Done! Restart the backend to load workers.")


if __name__ == "__main__":
    asyncio.run(reset_workers())
