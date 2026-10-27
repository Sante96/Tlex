"""API v1 routes."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_stream_user
from app.api.v1 import (
    anime,
    auth,
    backup,
    device_auth,
    downloads,
    franchises,
    images,
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
# The library and the TMDB proxies are for logged-in users only (the app is public
# through the tunnel); endpoints that personalise still read the user themselves.
_user_auth = [Depends(get_current_user)]
router.include_router(media.router, prefix="/media", tags=["media"], dependencies=_user_auth)
router.include_router(series.router, prefix="/series", tags=["series"], dependencies=_user_auth)
router.include_router(anime.router, prefix="/anime", tags=["anime"], dependencies=_user_auth)
router.include_router(seasons.router, prefix="/series", tags=["seasons"], dependencies=_user_auth)
router.include_router(
    franchises.router, prefix="/franchises", tags=["concerts"], dependencies=_user_auth
)
_stream_auth = [Depends(get_stream_user)]
router.include_router(stream.router, prefix="/stream", tags=["stream"], dependencies=_stream_auth)
router.include_router(
    subtitles.router, prefix="/subtitles", tags=["subtitles"], dependencies=_stream_auth
)
router.include_router(progress.router)
router.include_router(profiles.router)
router.include_router(watchlist.router)
router.include_router(people.router, dependencies=_user_auth)
# Own images: GET is public (random names, see app/services/images.py), adding needs login
router.include_router(images.router, prefix="/images", tags=["images"])
router.include_router(workers.router, tags=["workers"])
router.include_router(backup.router)
router.include_router(
    downloads.router, prefix="/downloads", tags=["downloads"], dependencies=_user_auth
)
# The seedbox agent has no user: its own token (SEEDBOX_AGENT_TOKEN)
router.include_router(downloads.agent_router, prefix="/downloads/agent", tags=["downloads"])
