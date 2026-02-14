"""Background scheduler for automatic scanning."""

import asyncio
from datetime import datetime, timedelta

import redis.asyncio as redis
from loguru import logger

from app.config import get_settings
from app.database import async_session_maker

settings = get_settings()

REDIS_KEY_INTERVAL = "tlex:scanner:interval_hours"


class AutoScanScheduler:
    """Scheduler for automatic periodic scanning."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_scan: datetime | None = None
        self._next_scan: datetime | None = None
        self._interval_hours: int = settings.scanner_auto_interval_hours
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(settings.redis_url)
        return self._redis

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_scan(self) -> datetime | None:
        return self._last_scan

    @property
    def next_scan(self) -> datetime | None:
        return self._next_scan

    @property
    def interval_hours(self) -> int:
        return self._interval_hours

    async def get_interval_hours(self) -> int:
        """Get interval from Redis or use default from settings."""
        try:
            r = await self._get_redis()
            value = await r.get(REDIS_KEY_INTERVAL)
            if value:
                self._interval_hours = int(value)
            else:
                self._interval_hours = settings.scanner_auto_interval_hours
        except Exception as e:
            logger.warning(f"Failed to get interval from Redis: {e}")
            self._interval_hours = settings.scanner_auto_interval_hours
        return self._interval_hours

    async def set_interval_hours(self, hours: int) -> None:
        """Set interval in Redis and update scheduler."""
        try:
            r = await self._get_redis()
            await r.set(REDIS_KEY_INTERVAL, str(hours))
            self._interval_hours = hours
            logger.info(f"Auto-scan interval set to {hours}h")
        except Exception as e:
            logger.error(f"Failed to set interval in Redis: {e}")

    async def start(self) -> None:
        """Start the auto-scan scheduler."""
        if self._running:
            logger.warning("Auto-scan scheduler already running")
            return

        self._running = True
        logger.info(f"Auto-scan scheduler starting with {self.interval_hours}h interval")

        while self._running:
            try:
                # Get current interval (may have been updated)
                interval_hours = await self.get_interval_hours()

                if interval_hours <= 0:
                    # Disabled - check again in 1 minute
                    self._next_scan = None
                    await asyncio.sleep(60)
                    continue

                # Calculate next scan time
                interval_seconds = interval_hours * 3600
                self._next_scan = datetime.now() + timedelta(hours=interval_hours)

                # Wait for the interval
                logger.debug(f"Next auto-scan in {interval_hours} hours at {self._next_scan}")
                await asyncio.sleep(interval_seconds)

                if not self._running:
                    break

                # Run the scan
                await self._run_scan()

            except asyncio.CancelledError:
                logger.info("Auto-scan scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Auto-scan scheduler error: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)

    async def stop(self) -> None:
        """Stop the auto-scan scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Auto-scan scheduler stopped")

    async def _run_scan(self) -> None:
        """Run a scan."""
        from app.services.scanner import scanner_service

        if scanner_service.is_scanning:
            logger.info("Skipping auto-scan: scan already in progress")
            return

        logger.info("Starting auto-scan...")
        self._last_scan = datetime.now()

        try:
            async with async_session_maker() as session:
                result = await scanner_service.scan_all_channels(session)

                if "error" in result:
                    logger.error(f"Auto-scan failed: {result['error']}")
                else:
                    logger.info(
                        f"Auto-scan completed: {result.get('new_items', 0)} new items, "
                        f"{result.get('updated_items', 0)} updated"
                    )
        except Exception as e:
            logger.error(f"Auto-scan error: {e}")

    async def get_status(self) -> dict:
        """Get scheduler status."""
        interval = await self.get_interval_hours()
        return {
            "enabled": interval > 0,
            "running": self._running,
            "interval_hours": interval,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "next_scan": self._next_scan.isoformat() if self._next_scan else None,
        }


# Singleton instance
auto_scan_scheduler = AutoScanScheduler()
