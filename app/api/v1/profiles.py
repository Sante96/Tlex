"""Profile management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import Profile, User
from app.models.worker import Worker, WorkerStatus
from app.schemas.profile import (
    ProfileCreate,
    ProfileListResponse,
    ProfileResponse,
    ProfileUpdate,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


async def _assign_worker_to_profile(session: AsyncSession, profile: Profile) -> bool:
    """
    Assign an available worker to a profile.

    Returns True if a worker was assigned, False otherwise.
    """
    # Find an active worker not assigned to any profile
    stmt = (
        select(Worker)
        .where(Worker.status == WorkerStatus.ACTIVE)
        .where(
            ~Worker.id.in_(
                select(Profile.worker_id).where(Profile.worker_id.isnot(None))
            )
        )
        .order_by(Worker.is_premium.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    worker = result.scalar_one_or_none()

    if worker:
        profile.worker_id = worker.id
        return True
    return False


@router.get("", response_model=ProfileListResponse)
async def get_profiles(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all profiles for the current user."""
    stmt = select(Profile).where(Profile.user_id == current_user.id)
    result = await session.execute(stmt)
    profiles = result.scalars().all()

    return ProfileListResponse(
        profiles=[ProfileResponse.from_orm_with_worker(p) for p in profiles],
        has_profiles=len(profiles) > 0,
    )


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: ProfileCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new profile for the current user.

    Automatically assigns an available worker to the profile.
    """
    # Check max profiles limit (e.g., 5 per user)
    stmt = select(Profile).where(Profile.user_id == current_user.id)
    result = await session.execute(stmt)
    existing_profiles = result.scalars().all()

    if len(existing_profiles) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Massimo 5 profili per utente",
        )

    # Create profile
    profile = Profile(
        user_id=current_user.id,
        name=data.name,
        avatar_url=data.avatar_url,
        is_kids=data.is_kids,
    )
    session.add(profile)

    # Try to assign a worker
    worker_assigned = await _assign_worker_to_profile(session, profile)

    await session.commit()
    await session.refresh(profile)

    if not worker_assigned:
        # Log warning but don't fail - profile can work without dedicated worker
        pass

    return ProfileResponse.from_orm_with_worker(profile)


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific profile."""
    stmt = select(Profile).where(
        Profile.id == profile_id,
        Profile.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profilo non trovato",
        )

    return ProfileResponse.from_orm_with_worker(profile)


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: int,
    data: ProfileUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a profile."""
    stmt = select(Profile).where(
        Profile.id == profile_id,
        Profile.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profilo non trovato",
        )

    # Update fields
    if data.name is not None:
        profile.name = data.name
    if data.avatar_url is not None:
        profile.avatar_url = data.avatar_url
    if data.is_kids is not None:
        profile.is_kids = data.is_kids
    if data.preferences is not None:
        profile.preferences = {**profile.preferences, **data.preferences}

    await session.commit()
    await session.refresh(profile)

    return ProfileResponse.from_orm_with_worker(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a profile."""
    stmt = select(Profile).where(
        Profile.id == profile_id,
        Profile.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profilo non trovato",
        )

    # Check if it's the last profile
    stmt = select(Profile).where(Profile.user_id == current_user.id)
    result = await session.execute(stmt)
    all_profiles = result.scalars().all()

    if len(all_profiles) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non puoi eliminare l'ultimo profilo",
        )

    await session.delete(profile)
    await session.commit()


@router.post("/{profile_id}/assign-worker", response_model=ProfileResponse)
async def assign_worker_to_profile(
    profile_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually assign a worker to a profile if one is available."""
    stmt = select(Profile).where(
        Profile.id == profile_id,
        Profile.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profilo non trovato",
        )

    if profile.worker_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il profilo ha già un worker assegnato",
        )

    worker_assigned = await _assign_worker_to_profile(session, profile)

    if not worker_assigned:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nessun worker disponibile",
        )

    await session.commit()
    await session.refresh(profile)

    return ProfileResponse.from_orm_with_worker(profile)
