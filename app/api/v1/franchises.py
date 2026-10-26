"""Franchises: the anime/game pages of the Concerts section, with their concerts."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, get_current_profile
from app.models.media import Franchise
from app.models.user import Profile, WatchProgress
from app.services.tmdb import tmdb_client

router = APIRouter()


class FranchiseUpdateBody(BaseModel):
    title: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None


def _images(franchise: Franchise) -> tuple[str | None, str | None]:
    """Its own poster and backdrop, else its newest concert's (a frame of the video):
    a game TMDB doesn't know still gets a picture."""
    pictured = (c for c in franchise.concerts if c.poster_path or c.backdrop_path)
    newest = max(pictured, key=lambda c: c.id, default=None)
    own = (newest.poster_path or newest.backdrop_path) if newest else None
    return (
        franchise.poster_path or own,
        franchise.backdrop_path or (newest.backdrop_path or own if newest else None),
    )


def _progress(wp: WatchProgress) -> dict:
    """The same shape as an episode's (series.py)."""
    return {
        "position_seconds": wp.position_seconds,
        "duration_seconds": wp.duration_seconds,
        "progress_percent": round(
            (wp.position_seconds / wp.duration_seconds * 100) if wp.duration_seconds else 0, 1
        ),
        "is_completed": wp.position_seconds >= wp.duration_seconds * 0.9
        if wp.duration_seconds
        else False,
    }


async def _franchise(session: DBSession, franchise_id: int) -> Franchise:
    franchise = (
        await session.execute(
            select(Franchise)
            .where(Franchise.id == franchise_id)
            .options(selectinload(Franchise.concerts))
        )
    ).scalar_one_or_none()
    if franchise is None:
        raise HTTPException(status_code=404, detail="Franchise not found")
    return franchise


async def _detail(session: DBSession, franchise: Franchise, profile: Profile) -> dict:
    progress = {
        wp.media_item_id: wp
        for wp in (
            await session.execute(
                select(WatchProgress).where(
                    WatchProgress.profile_id == profile.id,
                    WatchProgress.media_item_id.in_([c.id for c in franchise.concerts]),
                )
            )
        ).scalars()
    }
    # Newest first (undated last), then the last added
    concerts = sorted(
        franchise.concerts,
        key=lambda c: (c.release_date is None, -(c.release_date or date.min).toordinal(), -c.id),
    )
    poster_path, backdrop_path = _images(franchise)
    return {
        "id": franchise.id,
        "tmdb_id": franchise.tmdb_id,
        "title": franchise.title,
        "overview": franchise.overview,
        "poster_path": poster_path,
        "backdrop_path": backdrop_path,
        "concerts": [
            {
                "id": c.id,
                "title": c.title,
                "overview": c.overview,
                "poster_path": c.poster_path,
                "backdrop_path": c.backdrop_path,
                "release_date": str(c.release_date) if c.release_date else None,
                "duration_seconds": c.duration_seconds,
                "watch_progress": _progress(progress[c.id]) if c.id in progress else None,
            }
            for c in concerts
        ],
    }


@router.get("")
async def list_franchises(
    session: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str | None = None,
) -> dict:
    """The Concerts section: every anime/game, by name."""
    query = select(Franchise).options(selectinload(Franchise.concerts))
    count_query = select(func.count()).select_from(Franchise)
    if search:
        query = query.where(Franchise.title.ilike(f"%{search}%"))
        count_query = count_query.where(Franchise.title.ilike(f"%{search}%"))
    total = (await session.execute(count_query)).scalar() or 0
    franchises = (
        await session.execute(
            query.order_by(Franchise.title).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars()

    items = []
    for franchise in franchises:
        poster_path, backdrop_path = _images(franchise)
        items.append(
            {
                "id": franchise.id,
                "title": franchise.title,
                "poster_path": poster_path,
                "backdrop_path": backdrop_path,
                "concerts_count": len(franchise.concerts),
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{franchise_id}")
async def get_franchise(
    session: DBSession,
    franchise_id: int,
    profile: Profile = Depends(get_current_profile),
) -> dict:
    """An anime/game and its concerts, with the current profile's progress."""
    return await _detail(session, await _franchise(session, franchise_id), profile)


@router.patch("/{franchise_id}")
async def update_franchise(
    session: DBSession,
    franchise_id: int,
    body: FranchiseUpdateBody,
    profile: Profile = Depends(get_current_profile),
) -> dict:
    """Name, synopsis and images: the library's, so for everyone."""
    franchise = await _franchise(session, franchise_id)
    for name, value in body.model_dump(exclude_unset=True).items():
        setattr(franchise, name, value)
    await session.commit()
    return await _detail(session, await _franchise(session, franchise_id), profile)


@router.get("/{franchise_id}/tmdb-images")
async def get_franchise_tmdb_images(session: DBSession, franchise_id: int) -> dict:
    """TMDB's posters and backdrops of the anime, for the edit modal's pickers."""
    franchise = await _franchise(session, franchise_id)
    if not franchise.tmdb_id:
        return {"stills": [], "posters": [], "backdrops": []}
    images = await tmdb_client.get_tv_images(franchise.tmdb_id)
    return {
        "stills": [],
        "posters": images.get("posters", []),
        "backdrops": images.get("backdrops", []),
    }
