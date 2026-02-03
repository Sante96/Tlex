"""Worker Manager for Telegram account pool coordination."""

import asyncio
from datetime import timedelta

from loguru import logger
from pyrogram import Client
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.utils import utc_now
from app.models.worker import Worker, WorkerStatus

settings = get_settings()


class WorkerManager:
    """
    Manages the pool of Telegram worker accounts.

    Responsibilities:
    - Load and initialize all worker sessions
    - Select optimal worker for downloads (load balancing)
    - Handle FloodWait errors with automatic failover
    - Track worker load and status
    """

    def __init__(self) -> None:
        self._clients: dict[int, Client] = {}  # worker_id -> Client
        self._lock = asyncio.Lock()

    async def load_workers(self, session: AsyncSession) -> int:
        """
        Load all active workers from database and initialize clients.

        Returns:
            Number of successfully loaded workers.
        """
        stmt = select(Worker).where(Worker.status != WorkerStatus.OFFLINE)
        result = await session.execute(stmt)
        workers = result.scalars().all()

        loaded = 0
        for worker in workers:
            try:
                client = Client(
                    name=f"worker_{worker.id}",
                    api_id=settings.api_id,
                    api_hash=settings.api_hash,
                    session_string=worker.session_string,
                    in_memory=True,
                )
                await client.start()
                self._clients[worker.id] = client

                # Export and save updated session string to preserve MTProto state
                # This prevents BadMsgNotification errors after container restarts
                updated_session = await client.export_session_string()
                if updated_session != worker.session_string:
                    worker.session_string = updated_session
                    logger.debug(f"Updated session_string for worker {worker.id}")

                # Mark as active
                worker.status = WorkerStatus.ACTIVE
                await session.commit()

                loaded += 1
                logger.info(f"Loaded worker {worker.id} ({worker.phone_number})")
            except Exception as e:
                logger.error(f"Failed to load worker {worker.id}: {e}")
                worker.status = WorkerStatus.OFFLINE
                await session.commit()

        logger.info(f"Loaded {loaded}/{len(workers)} workers")
        return loaded

    async def get_best_worker(self, session: AsyncSession) -> tuple[Worker, Client] | None:
        """
        Get the optimal worker for a new download.

        Selection algorithm:
        1. Status must be ACTIVE
        2. Priority: Premium > Standard
        3. Lowest current_load first

        Returns:
            Tuple of (Worker, Client) or None if no workers available.
        """
        async with self._lock:
            # Check for recovered flood_wait workers
            await self._recover_flood_wait_workers(session)

            # Query best available worker (don't check load - HTTP connections may not close cleanly)
            stmt = (
                select(Worker)
                .where(Worker.status == WorkerStatus.ACTIVE)
                .order_by(Worker.is_premium.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            worker = result.scalar_one_or_none()

            if worker is None:
                logger.warning("No available workers!")
                return None

            if worker.id not in self._clients:
                logger.error(f"Worker {worker.id} not initialized")
                return None

            return worker, self._clients[worker.id]

    async def acquire_worker(self, session: AsyncSession, worker: Worker) -> None:
        """Increment worker load when starting a stream."""
        stmt = (
            update(Worker)
            .where(Worker.id == worker.id)
            .values(
                current_load=Worker.current_load + 1,
                last_used_at=utc_now(),
            )
        )
        await session.execute(stmt)
        await session.commit()

    async def release_worker(self, session: AsyncSession, worker: Worker) -> None:
        """Decrement worker load when stream ends."""
        stmt = (
            update(Worker)
            .where(Worker.id == worker.id)
            .values(
                current_load=Worker.current_load - 1,
            )
        )
        await session.execute(stmt)
        await session.commit()

    async def handle_flood_wait(
        self, session: AsyncSession, worker: Worker, wait_seconds: int
    ) -> tuple[Worker, Client] | None:
        """
        Handle FloodWait error with automatic failover.

        1. Mark current worker as FLOOD_WAIT
        2. Get a new worker from the pool
        3. Return new worker for retry

        Returns:
            New (Worker, Client) tuple or None if no workers available.
        """
        flood_until = utc_now() + timedelta(seconds=wait_seconds)

        logger.warning(f"Worker {worker.id} hit FloodWait ({wait_seconds}s), switching...")

        # Mark worker as flood_wait
        stmt = (
            update(Worker)
            .where(Worker.id == worker.id)
            .values(
                status=WorkerStatus.FLOOD_WAIT,
                flood_wait_until=flood_until,
                current_load=0,  # Reset load since it can't serve
            )
        )
        await session.execute(stmt)
        await session.commit()

        # Get new worker
        return await self.get_best_worker(session)

    async def _recover_flood_wait_workers(self, session: AsyncSession) -> None:
        """Check and recover workers whose flood wait has expired."""
        now = utc_now()

        stmt = (
            select(Worker)
            .where(Worker.status == WorkerStatus.FLOOD_WAIT)
            .where(Worker.flood_wait_until <= now)
        )
        result = await session.execute(stmt)
        workers = result.scalars().all()

        for worker in workers:
            logger.info(f"Recovering worker {worker.id} from FloodWait")
            worker.status = WorkerStatus.ACTIVE
            worker.flood_wait_until = None

        if workers:
            await session.commit()

    async def get_workers_status(self, session: AsyncSession) -> dict:
        """
        Get detailed status of all workers for monitoring/feedback.

        Returns:
            Dict with workers list and summary stats.
        """
        stmt = select(Worker)
        result = await session.execute(stmt)
        workers = result.scalars().all()

        now = utc_now()
        workers_info = []

        for w in workers:
            info = {
                "id": w.id,
                "phone": w.phone_number[-4:] if w.phone_number else "****",  # Last 4 digits only
                "is_premium": w.is_premium,
                "status": w.status.value,
                "current_load": w.current_load,
                "is_connected": w.id in self._clients,
            }

            # Add FloodWait details if applicable
            if w.status == WorkerStatus.FLOOD_WAIT and w.flood_wait_until:
                remaining = (w.flood_wait_until - now).total_seconds()
                info["flood_wait_remaining_seconds"] = max(0, int(remaining))
                info["flood_wait_until"] = w.flood_wait_until.isoformat()

            workers_info.append(info)

        # Summary
        active_count = sum(1 for w in workers_info if w["status"] == "active")
        flood_count = sum(1 for w in workers_info if w["status"] == "flood_wait")

        return {
            "workers": workers_info,
            "summary": {
                "total": len(workers_info),
                "active": active_count,
                "flood_wait": flood_count,
                "offline": len(workers_info) - active_count - flood_count,
                "connected_clients": len(self._clients),
            },
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown all worker clients."""
        for worker_id, client in self._clients.items():
            try:
                await client.stop()
                logger.info(f"Stopped worker {worker_id}")
            except Exception as e:
                logger.error(f"Error stopping worker {worker_id}: {e}")

        self._clients.clear()


# Global instance
worker_manager = WorkerManager()
