"""API v1 routes."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    media,
    profiles,
    progress,
    scanner,
    series,
    stream,
    subtitles,
    watchlist,
    workers,
)

router = APIRouter(prefix="/v1")
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(scanner.router, prefix="/scanner", tags=["scanner"])
router.include_router(media.router, prefix="/media", tags=["media"])
router.include_router(series.router, prefix="/series", tags=["series"])
router.include_router(stream.router, prefix="/stream", tags=["stream"])
router.include_router(subtitles.router, prefix="/subtitles", tags=["subtitles"])
router.include_router(progress.router)
router.include_router(profiles.router)
router.include_router(watchlist.router)
router.include_router(workers.router, tags=["workers"])

