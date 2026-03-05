"""Workers and Stats API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from pyrogram import Client
from pyrogram.errors import PasswordHashInvalid, SessionPasswordNeeded
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user, get_db
from app.config import get_settings
from app.core.worker_manager import worker_manager
from app.models import MediaItem, Profile, User
from app.models.media import MediaType
from app.models.worker import Worker, WorkerStatus

router = APIRouter()

# Temporary storage for pending auth flows (phone -> (Client, phone_code_hash))
# Client is kept alive so verify_code uses the same DC where send_code ran
_pending_auth: dict[str, tuple[Client, str]] = {}


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
    clients_total: int = 0
    clients_in_use: int = 0
    flood_wait_remaining_seconds: int | None = None
    flood_wait_until: str | None = None


class WorkersSummary(BaseModel):
    """Summary of all workers."""

    total: int
    active: int
    flood_wait: int
    offline: int
    connected_clients: int
    total_clients: int = 0
    clients_in_use: int = 0
    clients_available: int = 0


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
# Add Worker (2-step auth flow)
# ============================================================================
class SendCodeRequest(BaseModel):
    phone_number: str


class VerifyCodeRequest(BaseModel):
    phone_number: str
    code: str
    password: str | None = None  # 2FA password if needed


@router.post("/workers/send-code")
async def send_code(
    body: SendCodeRequest,
    _admin=Depends(get_admin_user),
) -> dict:
    """Step 1: Send verification code to phone number."""
    phone = body.phone_number.strip().replace(" ", "")

    # Clean up any previous pending auth for this phone
    if phone in _pending_auth:
        try:
            await _pending_auth[phone][0].stop()
        except Exception:
            pass
        del _pending_auth[phone]

    settings = get_settings()
    client = Client(
        name=f"add_worker_{phone}",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        in_memory=True,
    )

    try:
        await client.connect()
        sent_code = await client.send_code(phone)
        _pending_auth[phone] = (client, sent_code.phone_code_hash)
        logger.info(f"Sent verification code to {phone}")
        return {
            "status": "code_sent",
            "phone_code_hash": sent_code.phone_code_hash,
        }
    except Exception as e:
        logger.error(f"Failed to send code to {phone}: {e}")
        try:
            await client.stop()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/workers/verify-code")
async def verify_code(
    body: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_admin_user),
) -> dict:
    """Step 2: Verify code and create worker."""
    phone = body.phone_number.strip().replace(" ", "")

    if phone not in _pending_auth:
        raise HTTPException(status_code=400, detail="No pending auth for this phone. Send code first.")

    client, phone_code_hash = _pending_auth[phone]

    # Reconnect if TCP connection dropped while waiting for OTP
    if not client.is_connected:
        try:
            await client.connect()
        except Exception as e:
            del _pending_auth[phone]
            raise HTTPException(status_code=400, detail=f"Lost connection, please send code again: {e}") from None

    signed_in_user = None
    try:
        signed_in_user = await client.sign_in(phone, phone_code_hash, body.code)
    except PasswordHashInvalid:
        raise HTTPException(status_code=400, detail="Password 2FA errata") from None
    except SessionPasswordNeeded:
        if not body.password:
            return {"status": "2fa_required"}
        try:
            await client.check_password(body.password)
        except PasswordHashInvalid:
            raise HTTPException(status_code=400, detail="Password 2FA errata") from None
        except Exception as e2:
            raise HTTPException(status_code=400, detail=f"2FA failed: {e2}") from None
    except Exception as e:
        # Don't stop the client on sign_in failure — user may retry with a new code
        # Only clean up on fatal auth errors
        error_str = str(e)
        if any(x in error_str for x in ("PHONE_CODE_INVALID", "PHONE_CODE_EXPIRED", "SESSION_PASSWORD_NEEDED")):
            pass  # Keep client alive for retry
        else:
            del _pending_auth[phone]
            try:
                await client.stop()
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}") from None

    try:
        # export_session_string reads from in-memory storage — no active connection needed
        session_string = await client.export_session_string()

        # get_me() gives accurate is_premium; sign_in() response may omit the flag
        # Reconnect if DC migration terminated the connection
        is_premium = bool(getattr(signed_in_user, "is_premium", False))
        try:
            if not client.is_connected:
                await client.connect()
            me = await client.get_me()
            is_premium = bool(me.is_premium)
        except Exception:
            pass  # Fall back to sign_in value

        # Check if worker already exists
        existing = await db.execute(select(Worker).where(Worker.phone_number == phone))
        if existing.scalar_one_or_none():
            del _pending_auth[phone]
            try:
                await client.stop()
            except Exception:
                pass
            raise HTTPException(status_code=400, detail="Worker with this phone already exists")

        # Save to DB
        worker = Worker(
            session_string=session_string,
            phone_number=phone,
            is_premium=is_premium,
            max_concurrent_streams=4 if is_premium else 2,
            status=WorkerStatus.ACTIVE,
        )
        db.add(worker)
        await db.commit()
        await db.refresh(worker)

        # Stop the temp client — ignore if already terminated after DC migration
        try:
            await client.stop()
        except Exception:
            pass
        del _pending_auth[phone]

        # Reload workers to pick up the new one
        await worker_manager.shutdown()
        await worker_manager.load_workers(db)

        logger.info(f"Added new worker: {phone} (premium={is_premium})")
        return {
            "status": "ok",
            "worker_id": worker.id,
            "is_premium": is_premium,
        }
    except HTTPException:
        raise
    except Exception as e:
        _pending_auth.pop(phone, None)
        try:
            await client.stop()
        except Exception:
            pass
        logger.error(f"Failed to create worker for {phone}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.delete("/workers/{worker_id}")
async def delete_worker(
    worker_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_admin_user),
) -> dict:
    """Remove a worker from the system."""
    result = await db.execute(select(Worker).where(Worker.id == worker_id))
    worker = result.scalar_one_or_none()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    phone = worker.phone_number
    await db.delete(worker)
    await db.commit()

    # Reload workers
    await worker_manager.shutdown()
    async with db.begin():
        await worker_manager.load_workers(db)

    logger.info(f"Deleted worker {worker_id} ({phone})")
    return {"status": "ok"}


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
