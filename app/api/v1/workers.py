"""Workers and Stats API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.worker_manager import worker_manager
from app.models import MediaItem, Profile, User
from app.models.media import MediaType

router = APIRouter()


# ============================================================================
# Workers Status
# ============================================================================
class WorkerInfo(BaseModel):
    """Individual worker status."""

    id: int
    phone: str
    is_premium: bool
    status: str
    current_load: int
    is_connected: bool
    flood_wait_remaining_seconds: int | None = None
    flood_wait_until: str | None = None


class WorkersSummary(BaseModel):
    """Summary of all workers."""

    total: int
    active: int
    flood_wait: int
    offline: int
    connected_clients: int


class WorkersStatusResponse(BaseModel):
    """Workers status response."""

    workers: list[WorkerInfo]
    summary: WorkersSummary


@router.get("/workers/status", response_model=WorkersStatusResponse)
async def get_workers_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get status of all Telegram workers."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    status = await worker_manager.get_workers_status(db)

    return WorkersStatusResponse(
        workers=[WorkerInfo(**w) for w in status["workers"]],
        summary=WorkersSummary(**status["summary"]),
    )


# ============================================================================
# System Stats
# ============================================================================
class MediaStats(BaseModel):
    """Media statistics."""

    movies: int
    episodes: int
    total: int


class UserStats(BaseModel):
    """User statistics."""

    total: int
    profiles: int


class SystemStatsResponse(BaseModel):
    """System statistics response."""

    media: MediaStats
    users: UserStats
    workers: WorkersSummary


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get overall system statistics."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Count media
    movies_result = await db.execute(
        select(func.count()).where(MediaItem.media_type == MediaType.MOVIE)
    )
    movies_count = movies_result.scalar() or 0

    episodes_result = await db.execute(
        select(func.count()).where(MediaItem.media_type == MediaType.EPISODE)
    )
    episodes_count = episodes_result.scalar() or 0

    # Count users and profiles
    users_result = await db.execute(select(func.count()).select_from(User))
    users_count = users_result.scalar() or 0

    profiles_result = await db.execute(select(func.count()).select_from(Profile))
    profiles_count = profiles_result.scalar() or 0

    # Workers summary
    workers_status = await worker_manager.get_workers_status(db)

    return SystemStatsResponse(
        media=MediaStats(
            movies=movies_count,
            episodes=episodes_count,
            total=movies_count + episodes_count,
        ),
        users=UserStats(
            total=users_count,
            profiles=profiles_count,
        ),
        workers=WorkersSummary(**workers_status["summary"]),
    )
