"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app._version import __version__
from app.api.v1 import router as api_v1_router
from app.config import get_settings
from app.core import pyrogram_tuning
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.core.worker_manager import worker_manager
from app.database import async_session_maker, create_all_tables, engine

settings = get_settings()

# Configure logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    import asyncio

    # Startup
    logger.info("Starting TLEX...")

    # Ensure all tables exist (creates new ones without touching existing)
    await create_all_tables()

    # Load workers (Pyrogram tuned first: the tweaks apply to connections opened later)
    pyrogram_tuning.apply()
    async with async_session_maker() as session:
        count = await worker_manager.load_workers(session)
        logger.info(f"Loaded {count} Telegram workers")

    # Start background cache population (fire and forget)
    async def populate_caches_background():
        try:
            # Wait for app to be fully ready
            await asyncio.sleep(5)
            async with async_session_maker() as session:
                from app.services.subtitles.cache import populate_all_caches

                await populate_all_caches(session)
        except Exception as e:
            logger.warning(f"Background cache population failed: {e}")

    # The chapters of titles scanned before they were stored: once, in the background
    async def backfill_chapters_background():
        try:
            await asyncio.sleep(30)  # after the subtitle pass and the first viewers
            from app.services.chapters import backfill_chapters

            await backfill_chapters()
        except Exception as e:
            logger.warning(f"Chapter backfill failed: {e}")

    # A frame of the video for the concerts without an image (one at a time, after the
    # chapters pass has had its turn)
    async def backfill_concert_frames_background():
        try:
            await asyncio.sleep(60)
            from app.services.concert_frames import backfill_concert_frames

            await backfill_concert_frames()
        except Exception as e:
            logger.warning(f"Concert frames failed: {e}")

    # Series and films from before the Anime section: their language from TMDB, once
    async def classify_library_background():
        try:
            await asyncio.sleep(20)
            from app.services.anime import classify_library

            async with async_session_maker() as session:
                await classify_library(session)
        except Exception as e:
            logger.warning(f"Anime classification failed: {e}")

    # Kept: the loop holds only weak references to tasks, and shutdown cancels them
    background = [
        asyncio.create_task(classify_library_background()),
        asyncio.create_task(populate_caches_background()),
        asyncio.create_task(backfill_chapters_background()),
        asyncio.create_task(backfill_concert_frames_background()),
    ]
    logger.info("Background subtitle cache population started")

    # Start auto-scan scheduler (always on: it idles while the interval is 0, and the
    # interval can be enabled later from the admin UI)
    from app.services.scheduler import auto_scan_scheduler, backup_sync_scheduler

    background.append(asyncio.create_task(auto_scan_scheduler.start()))
    logger.info("Auto-scan scheduler started")

    # Start backup sync scheduler (always on, interval managed via Redis)
    background.append(asyncio.create_task(backup_sync_scheduler.start()))
    logger.info("Backup sync scheduler started")

    # Background cleanup for stale stream readers (safety net)
    async def stream_reader_cleanup_loop():
        from app.services.streaming.manager import cleanup_stale_readers

        while True:
            await asyncio.sleep(30)
            try:
                await cleanup_stale_readers()
            except Exception as e:
                logger.warning(f"Stream reader cleanup error: {e}")

    background.append(asyncio.create_task(stream_reader_cleanup_loop()))

    yield

    # Shutdown
    logger.info("Shutting down TLEX...")
    for task in background:
        task.cancel()
    await worker_manager.shutdown()
    await engine.dispose()
    logger.info("Goodbye!")


app = FastAPI(
    title="TLEX - Telegram Media Server",
    description="Self-hosted streaming platform using Telegram as storage backend",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # pyright: ignore[reportArgumentType]

# CORS middleware - use configured origins, with fallback to localhost in debug
cors_origins = settings.cors_origins_list if settings.cors_origins_list else []
if settings.debug and not cors_origins:
    cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": "TLEX",
        "version": __version__,
        "status": "running",
        "environment": settings.environment,
    }


@app.get("/health")
async def health():
    """Detailed health check with component status."""
    import redis.asyncio as redis
    from sqlalchemy import text

    health_status = {
        "status": "healthy",
        "components": {},
    }

    # Check database
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        health_status["components"]["database"] = {"status": "healthy"}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = {"status": "unhealthy", "error": str(e)}

    # Check Redis
    try:
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()  # pyright: ignore[reportGeneralTypeIssues]  (redis-py types it sync)
        await redis_client.close()
        health_status["components"]["redis"] = {"status": "healthy"}
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["redis"] = {"status": "unhealthy", "error": str(e)}

    # Check workers
    worker_count = len(worker_manager._clients)
    if worker_count > 0:
        health_status["components"]["workers"] = {
            "status": "healthy",
            "count": worker_count,
        }
    else:
        health_status["status"] = "degraded"
        health_status["components"]["workers"] = {
            "status": "unhealthy",
            "count": 0,
            "error": "No workers available",
        }

    return health_status


# Include API routers
app.include_router(api_v1_router, prefix="/api")
