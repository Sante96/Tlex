"""API v1 routes."""

from fastapi import APIRouter, Depends

from app.api.deps import get_stream_user
from app.api.v1 import (
    auth,
    backup,
    device_auth,
    media,
    people,
    profiles,
    progress,
    scanner,
    seasons,
    series,
    stream,
    subtitles,
    watchlist,
    workers,
)

router = APIRouter(prefix="/v1")
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(device_auth.router, prefix="/auth", tags=["auth"])
router.include_router(scanner.router, prefix="/scanner", tags=["scanner"])
router.include_router(media.router, prefix="/media", tags=["media"])
router.include_router(series.router, prefix="/series", tags=["series"])
router.include_router(seasons.router, prefix="/series", tags=["seasons"])
_stream_auth = [Depends(get_stream_user)]
router.include_router(stream.router, prefix="/stream", tags=["stream"], dependencies=_stream_auth)
router.include_router(
    subtitles.router, prefix="/subtitles", tags=["subtitles"], dependencies=_stream_auth
)
router.include_router(progress.router)
router.include_router(profiles.router)
router.include_router(watchlist.router)
router.include_router(people.router)
router.include_router(workers.router, tags=["workers"])
router.include_router(backup.router)

