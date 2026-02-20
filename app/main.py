"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.deps import DBSession
from app.api.v1 import router as api_v1_router
from app.config import get_settings
from app.core.exceptions import TLEXException, tlex_exception_handler
from app.core.logging import setup_logging
from app.core.metrics import get_metrics_response
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

    # Load workers
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

    asyncio.create_task(populate_caches_background())
    logger.info("Background subtitle cache population started")

    # Start auto-scan scheduler if enabled
    from app.services.scheduler import auto_scan_scheduler
    if settings.scanner_auto_interval_hours > 0:
        asyncio.create_task(auto_scan_scheduler.start())
        logger.info(f"Auto-scan scheduler started (interval: {settings.scanner_auto_interval_hours}h)")

    # Background cleanup for stale stream readers (safety net)
    async def stream_reader_cleanup_loop():
        from app.services.streaming.manager import cleanup_stale_readers
        while True:
            await asyncio.sleep(30)
            try:
                await cleanup_stale_readers()
            except Exception as e:
                logger.warning(f"Stream reader cleanup error: {e}")

    cleanup_task = asyncio.create_task(stream_reader_cleanup_loop())

    # Keepalive: send MTProto Ping to all Pyrogram clients every 60s to prevent TCP idle timeout
    # Pyrogram closes connections after ~2min of inactivity → OSError on next stream_media call
    # Use raw Ping (not get_me) to avoid FLOOD_WAIT on high-session accounts
    async def client_keepalive_loop():
        from pyrogram import raw

        while True:
            await asyncio.sleep(30)
            for _worker_id, client in worker_manager._client_pool:
                # Ping main session
                try:
                    await client.invoke(raw.functions.Ping(ping_id=0))
                except Exception as e:
                    logger.debug(f"Keepalive main ping failed for client {id(client)}: {e}")
                # Ping all media sessions (used by stream_media/get_file — separate DC connections)
                # If ping fails, drop the session so it gets recreated fresh on next get_file call
                media_sessions = getattr(client, "media_sessions", {})
                for dc_id, media_session in list(media_sessions.items()):
                    try:
                        await media_session.invoke(raw.functions.Ping(ping_id=0))
                    except Exception as e:
                        logger.debug(f"Keepalive: dropping stale media session DC{dc_id} for client {id(client)}: {e}")
                        try:
                            await media_session.stop()
                        except Exception:
                            pass
                        media_sessions.pop(dc_id, None)

    keepalive_task = asyncio.create_task(client_keepalive_loop())

    yield

    cleanup_task.cancel()
    keepalive_task.cancel()

    # Shutdown
    logger.info("Shutting down TLEX...")
    await worker_manager.shutdown()
    await engine.dispose()
    logger.info("Goodbye!")


app = FastAPI(
    title="TLEX - Telegram Media Server",
    description="Self-hosted streaming platform using Telegram as storage backend",
    version="1.2.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(TLEXException, tlex_exception_handler)

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
        "version": "1.0.3",
        "status": "running",
        "environment": settings.environment,
    }


@app.get("/workers/status")
async def workers_status(session: DBSession):
    """Get detailed status of all Telegram workers including FloodWait info."""
    return await worker_manager.get_workers_status(session)


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics_response()


@app.get("/stats")
async def stats(session: DBSession):
    """System stats for frontend dashboard."""
    from sqlalchemy import func, select

    from app.models.media import MediaItem, MediaType
    from app.models.user import Profile, User

    # Count media items
    movies_count = await session.scalar(
        select(func.count()).select_from(MediaItem).where(MediaItem.media_type == MediaType.MOVIE)
    )
    episodes_count = await session.scalar(
        select(func.count()).select_from(MediaItem).where(MediaItem.media_type == MediaType.EPISODE)
    )

    # Count users and profiles
    users_count = await session.scalar(select(func.count()).select_from(User))
    profiles_count = await session.scalar(select(func.count()).select_from(Profile))

    # Workers status
    workers_data = await worker_manager.get_workers_status(session)

    return {
        "media": {
            "movies": movies_count or 0,
            "episodes": episodes_count or 0,
            "total": (movies_count or 0) + (episodes_count or 0),
        },
        "users": {
            "total": users_count or 0,
            "profiles": profiles_count or 0,
        },
        "workers": workers_data["summary"],
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
        await redis_client.ping()
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
