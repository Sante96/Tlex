"""Watch progress API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import MediaItem, Series, User, WatchProgress

router = APIRouter(prefix="/progress", tags=["progress"])


class ProgressUpdate(BaseModel):
    """Request body for updating watch progress."""

    position_seconds: int
    duration_seconds: int


class ProgressResponse(BaseModel):
    """Response for watch progress."""

    media_item_id: int
    position_seconds: int
    duration_seconds: int
    progress_percent: float
    completed: bool


class ContinueWatchingItem(BaseModel):
    """Item in continue watching list."""

    id: int
    title: str
    poster_path: str | None
    backdrop_path: str | None
    media_type: str
    position_seconds: int
    duration_seconds: int
    progress_percent: float
    # Series metadata for Plex-style grouping
    series_id: int | None = None
    series_title: str | None = None
    series_poster_path: str | None = None
    season_number: int | None = None
    episode_number: int | None = None


@router.get("/{media_id}", response_model=ProgressResponse | None)
async def get_progress(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get watch progress for a specific media item."""
    result = await db.execute(
        select(WatchProgress).where(
            WatchProgress.user_id == current_user.id,
            WatchProgress.media_item_id == media_id,
        )
    )
    progress = result.scalar_one_or_none()

    if not progress:
        return None

    return ProgressResponse(
        media_item_id=progress.media_item_id,
        position_seconds=progress.position_seconds,
        duration_seconds=progress.duration_seconds,
        progress_percent=progress.progress_percent,
        completed=progress.completed,
    )


@router.put("/{media_id}", response_model=ProgressResponse)
async def update_progress(
    media_id: int,
    data: ProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update watch progress for a media item."""
    # Verify media exists
    media_result = await db.execute(select(MediaItem).where(MediaItem.id == media_id))
    media = media_result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    # Get or create progress
    result = await db.execute(
        select(WatchProgress).where(
            WatchProgress.user_id == current_user.id,
            WatchProgress.media_item_id == media_id,
        )
    )
    progress = result.scalar_one_or_none()

    if not progress:
        progress = WatchProgress(
            user_id=current_user.id,
            media_item_id=media_id,
            position_seconds=data.position_seconds,
            duration_seconds=data.duration_seconds,
        )
        db.add(progress)
    else:
        progress.position_seconds = data.position_seconds
        progress.duration_seconds = data.duration_seconds

    # Mark as completed if watched > 90%
    if data.duration_seconds > 0:
        percent = (data.position_seconds / data.duration_seconds) * 100
        progress.completed = percent >= 90

    await db.commit()
    await db.refresh(progress)

    return ProgressResponse(
        media_item_id=progress.media_item_id,
        position_seconds=progress.position_seconds,
        duration_seconds=progress.duration_seconds,
        progress_percent=progress.progress_percent,
        completed=progress.completed,
    )


@router.get("", response_model=list[ContinueWatchingItem])
async def get_continue_watching(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 10,
):
    """Get list of media items to continue watching.

    For episodes: groups by series and returns the first incomplete episode
    (earliest season/episode number). Uses series poster for display.
    For movies: returns individual items.
    """
    # Get all incomplete progress items with media and series info
    result = await db.execute(
        select(WatchProgress, MediaItem, Series)
        .join(MediaItem, WatchProgress.media_item_id == MediaItem.id)
        .outerjoin(Series, MediaItem.series_id == Series.id)
        .where(
            WatchProgress.user_id == current_user.id,
            WatchProgress.completed == False,  # noqa: E712
            WatchProgress.position_seconds > 0,
        )
        .order_by(WatchProgress.updated_at.desc())
    )
    rows = result.all()

    # Group episodes by series, keep first incomplete per series
    seen_series: dict[int, bool] = {}  # series_id -> already added
    items: list[ContinueWatchingItem] = []

    for progress, media, series in rows:
        # Movies: always include individually
        if media.series_id is None:
            items.append(
                ContinueWatchingItem(
                    id=media.id,
                    title=media.title,
                    poster_path=media.poster_path,
                    backdrop_path=media.backdrop_path,
                    media_type=media.media_type.value,
                    position_seconds=progress.position_seconds,
                    duration_seconds=progress.duration_seconds,
                    progress_percent=progress.progress_percent,
                )
            )
        else:
            # Episodes: only one per series (first incomplete by S:E order)
            if media.series_id not in seen_series:
                seen_series[media.series_id] = True
                items.append(
                    ContinueWatchingItem(
                        id=media.id,
                        title=media.title,
                        poster_path=series.poster_path if series else media.poster_path,
                        backdrop_path=series.backdrop_path if series else media.backdrop_path,
                        media_type=media.media_type.value,
                        position_seconds=progress.position_seconds,
                        duration_seconds=progress.duration_seconds,
                        progress_percent=progress.progress_percent,
                        series_id=media.series_id,
                        series_title=series.title if series else None,
                        series_poster_path=series.poster_path if series else None,
                        season_number=media.season_number,
                        episode_number=media.episode_number,
                    )
                )

        if len(items) >= limit:
            break

    return items


@router.delete("/{media_id}")
async def delete_progress(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete watch progress (mark as not started)."""
    result = await db.execute(
        select(WatchProgress).where(
            WatchProgress.user_id == current_user.id,
            WatchProgress.media_item_id == media_id,
        )
    )
    progress = result.scalar_one_or_none()

    if progress:
        await db.delete(progress)
        await db.commit()

    return {"status": "ok"}
