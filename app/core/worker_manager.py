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

# Number of Pyrogram clients to create per worker account
# Benchmarked: Premium peaks at 6 clients (~45 MB/s), Standard at 4 (~16 MB/s)
CLIENTS_PER_WORKER_PREMIUM = 6
CLIENTS_PER_WORKER_STANDARD = 4

# Max clients a single stream can dynamically acquire
# Streams start with 1 and scale up as they continue
MAX_CLIENTS_PER_STREAM = 6


class WorkerManager:
    """
    Manages the pool of Telegram worker accounts.

    Responsibilities:
    - Load and initialize all worker sessions
    - Select optimal worker for downloads (load balancing)
    - Handle FloodWait errors with automatic failover
    - Track worker load and status
    - Create multiple clients per worker for concurrent streams
    """

    def __init__(self) -> None:
        self._clients: dict[int, Client] = {}  # worker_id -> primary Client
        self._client_pool: list[tuple[int, Client]] = []  # [(worker_id, client), ...] all clients
        self._client_in_use: dict[int, bool] = {}  # id(client) -> is_in_use
        self._worker_loads: dict[int, int] = {}  # worker_id -> current_load
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
                # Create primary client
                primary_client = Client(
                    name=f"worker_{worker.id}",
                    api_id=settings.api_id,
                    api_hash=settings.api_hash,
                    session_string=worker.session_string,
                    in_memory=True,
                )
                await primary_client.start()
                self._clients[worker.id] = primary_client
                self._client_pool.append((worker.id, primary_client))
                self._client_in_use[id(primary_client)] = False

                # Export and save updated session string to preserve MTProto state
                updated_session = await primary_client.export_session_string()
                if updated_session != worker.session_string:
                    worker.session_string = updated_session
                    logger.debug(f"Updated session_string for worker {worker.id}")

                # Create additional clients for concurrent streams
                # Premium accounts get more clients due to higher bandwidth
                max_extra = (CLIENTS_PER_WORKER_PREMIUM if worker.is_premium else CLIENTS_PER_WORKER_STANDARD) - 1

                # Load existing extra sessions or create new ones
                extra_sessions = worker.extra_sessions or []
                sessions_updated = False

                for i in range(max_extra):
                    try:
                        if i < len(extra_sessions):
                            # Use existing saved session
                            extra_session = extra_sessions[i]
                            logger.debug(f"Loading saved session {i+1} for worker {worker.id}")
                        else:
                            # Create new session from primary (first time)
                            extra_session = worker.session_string
                            logger.debug(f"Creating new session {i+1} for worker {worker.id}")

                        extra_client = Client(
                            name=f"worker_{worker.id}_stream_{i+1}",
                            api_id=settings.api_id,
                            api_hash=settings.api_hash,
                            session_string=extra_session,
                            in_memory=True,
                        )
                        await extra_client.start()

                        # Export and save the session (may have changed after start)
                        new_session = await extra_client.export_session_string()
                        if i < len(extra_sessions):
                            if extra_sessions[i] != new_session:
                                extra_sessions[i] = new_session
                                sessions_updated = True
                        else:
                            extra_sessions.append(new_session)
                            sessions_updated = True

                        self._client_pool.append((worker.id, extra_client))
                        self._client_in_use[id(extra_client)] = False
                        logger.debug(f"Started extra client {i+1} for worker {worker.id}")
                    except Exception as e:
                        logger.warning(f"Failed to create extra client {i+1} for worker {worker.id}: {e}")
                        break  # Stop creating more if one fails

                # Save updated sessions to DB
                if sessions_updated:
                    worker.extra_sessions = extra_sessions
                    logger.info(f"Saved {len(extra_sessions)} extra sessions for worker {worker.id}")

                total_clients = len([c for wid, c in self._client_pool if wid == worker.id])
                logger.info(
                    f"Worker {worker.id}: {total_clients} clients "
                    f"({'premium' if worker.is_premium else 'standard'})"
                )

                # Mark as active
                worker.status = WorkerStatus.ACTIVE
                await session.commit()

                loaded += 1
                logger.info(f"Loaded worker {worker.id} ({worker.phone_number})")
            except Exception as e:
                logger.error(f"Failed to load worker {worker.id}: {e}")
                worker.status = WorkerStatus.OFFLINE
                await session.commit()

        logger.info(f"Loaded {loaded}/{len(workers)} workers ({len(self._client_pool)} total clients)")
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

    async def get_best_workers(self, session: AsyncSession, limit: int = 3) -> list[tuple[Worker, Client]]:
        """
        Get a pool of optimal workers for striping (parallel downloads).

        Returns up to `limit` active workers, prioritizing premium ones.
        """
        async with self._lock:
            await self._recover_flood_wait_workers(session)

            # Get multiple workers
            stmt = (
                select(Worker)
                .where(Worker.status == WorkerStatus.ACTIVE)
                .order_by(Worker.is_premium.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            workers = result.scalars().all()

            results = []
            for worker in workers:
                if worker.id in self._clients:
                    results.append((worker, self._clients[worker.id]))

            if not results:
                logger.warning("No available workers for striping!")

            return results

    async def get_available_clients(self, limit: int = 1) -> list[Client]:
        """
        Get available worker clients without DB session (for streaming).

        Returns up to `limit` initialized clients that are NOT currently in use.
        Marks returned clients as "in use" to prevent concurrent operations.
        Uses the expanded client pool (multiple clients per worker).

        IMPORTANT: Uses async lock to prevent race conditions.
        """
        async with self._lock:
            available = []
            for worker_id, client in self._client_pool:
                client_id = id(client)
                if not self._client_in_use.get(client_id, False):
                    available.append((worker_id, client))
                    if len(available) >= limit:
                        break

            if not available:
                total_clients = len(self._client_pool)
                in_use = sum(1 for v in self._client_in_use.values() if v)
                logger.warning(f"[POOL] No available clients! {in_use}/{total_clients} in use.")
                return []

            # Mark as in use and return clients (inside lock to prevent race)
            result = []
            for _worker_id, client in available:
                self._client_in_use[id(client)] = True
                result.append(client)

            in_use = sum(1 for v in self._client_in_use.values() if v)
            total = len(self._client_pool)
            logger.info(f"[POOL] Acquired {len(result)} client(s), pool={in_use}/{total} in use")
            return result

    def pool_pressure(self) -> float:
        """
        Return pool usage ratio (0.0 = all free, 1.0 = all in use).

        Used by readers to decide when to voluntarily release excess clients.
        """
        total = len(self._client_pool)
        if total == 0:
            return 1.0
        in_use = sum(1 for v in self._client_in_use.values() if v)
        return in_use / total

    async def try_acquire_one(self) -> Client | None:
        """
        Try to acquire one additional client from the pool (non-blocking).

        Used for dynamic scaling: streams start with 1 client and
        progressively acquire more as they continue.

        Returns:
            A single Client or None if no clients available.
        """
        async with self._lock:
            for worker_id, client in self._client_pool:
                client_id = id(client)
                if not self._client_in_use.get(client_id, False):
                    self._client_in_use[client_id] = True
                    logger.debug(f"Dynamic acquire: client {client_id} (worker {worker_id})")
                    return client
            return None

    def release_clients(self, clients: list[Client]) -> None:
        """
        Release clients back to the pool after streaming is done.

        Must be called when streaming completes to allow reuse.
        """
        for client in clients:
            client_id = id(client)
            if client_id in self._client_in_use:
                self._client_in_use[client_id] = False

        in_use = sum(1 for v in self._client_in_use.values() if v)
        total = len(self._client_pool)
        logger.info(f"[POOL] Released {len(clients)} client(s), pool={in_use}/{total} in use")

    async def acquire_worker(self, session: AsyncSession, worker: Worker) -> None:
        """Increment worker load when starting a stream."""
        # Update in-memory load
        self._worker_loads[worker.id] = self._worker_loads.get(worker.id, 0) + 1

        # We don't update DB for every stream to avoid write contention
        # But we update last_used_at
        stmt = (
            update(Worker)
            .where(Worker.id == worker.id)
            .values(last_used_at=utc_now())
        )
        await session.execute(stmt)
        await session.commit()

    async def release_worker(self, worker_id: int) -> None:
        """Decrement worker load when stream ends."""
        # Update in-memory load
        if worker_id in self._worker_loads:
            self._worker_loads[worker_id] = max(0, self._worker_loads[worker_id] - 1)

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
            # Count clients for this worker
            worker_clients = [(wid, c) for wid, c in self._client_pool if wid == w.id]
            clients_in_use = sum(1 for wid, c in worker_clients if self._client_in_use.get(id(c), False))

            info = {
                "id": w.id,
                "phone": w.phone_number[-4:] if w.phone_number else "****",  # Last 4 digits only
                "is_premium": w.is_premium,
                "status": w.status.value,
                "current_load": self._worker_loads.get(w.id, 0),
                "is_connected": w.id in self._clients,
                "clients_total": len(worker_clients),
                "clients_in_use": clients_in_use,
            }

            # Add FloodWait details if applicable
            if w.status == WorkerStatus.FLOOD_WAIT and w.flood_wait_until:
                remaining = (w.flood_wait_until - now).total_seconds()
                info["flood_wait_remaining_seconds"] = max(0, int(remaining))
                info["flood_wait_until"] = w.flood_wait_until.isoformat()

            workers_info.append(info)

        # Summary
        active_count = sum(1 for w in workers_info if w["status"] == "ACTIVE")
        flood_count = sum(1 for w in workers_info if w["status"] == "FLOOD_WAIT")

        # Client pool stats
        total_clients = len(self._client_pool)
        clients_in_use = sum(1 for v in self._client_in_use.values() if v)

        return {
            "workers": workers_info,
            "summary": {
                "total": len(workers_info),
                "active": active_count,
                "flood_wait": flood_count,
                "offline": len(workers_info) - active_count - flood_count,
                "connected_clients": len(self._clients),
                "total_clients": total_clients,
                "clients_in_use": clients_in_use,
                "clients_available": total_clients - clients_in_use,
            },
        }

    def pool_status(self) -> dict:
        """
        Lightweight pool status (no DB session required).

        Returns client pool usage info for frontend warnings.
        """
        total = len(self._client_pool)
        in_use = sum(1 for v in self._client_in_use.values() if v)
        available = total - in_use
        pressure = in_use / total if total > 0 else 1.0
        return {
            "total_clients": total,
            "clients_in_use": in_use,
            "clients_available": available,
            "pool_pressure": round(pressure, 2),
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown all worker clients."""
        # Stop all clients in the pool
        for worker_id, client in self._client_pool:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"Error stopping client for worker {worker_id}: {e}")

        logger.info(f"Stopped {len(self._client_pool)} clients")
        self._clients.clear()
        self._client_pool.clear()
        self._client_in_use.clear()


# Global instance
worker_manager = WorkerManager()
