"""Backup channel API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DBSession, get_admin_user
from app.core.worker_manager import worker_manager
from app.models.backup import BackupChannel
from app.services.backup.service import backup_service

router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("/sync-interval")
async def get_sync_interval(_admin=Depends(get_admin_user)) -> dict:
    """Get the current backup sync interval."""
    from app.services.scheduler import backup_sync_scheduler

    interval = await backup_sync_scheduler.get_interval_hours()
    return {"interval_hours": interval}


@router.post("/sync-interval")
async def set_sync_interval(hours: int, _admin=Depends(get_admin_user)) -> dict:
    """Set the backup sync interval in hours (0 = disabled)."""
    from app.services.scheduler import backup_sync_scheduler

    await backup_sync_scheduler.set_interval_hours(hours)
    return {"interval_hours": hours}


class CreateBackupRequest(BaseModel):
    main_channel_id: int
    title: str
    invite_members: bool = True


class BackupTopicOut(BaseModel):
    main_topic_id: int
    backup_topic_id: int
    name: str


class BackupChannelOut(BaseModel):
    id: int
    main_channel_id: int
    backup_channel_id: int
    title: str
    is_active: bool
    is_promoted: bool
    synced_count: int
    last_sync_at: str | None
    failure_count: int
    max_failures: int
    last_failure_at: str | None
    topics: list[BackupTopicOut]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj: BackupChannel) -> "BackupChannelOut":
        topics: list[BackupTopicOut] = []
        if obj.topic_map:
            for main_id_str, entry in obj.topic_map.items():
                if not entry.get("backup_id"):
                    continue
                topics.append(BackupTopicOut(
                    main_topic_id=int(main_id_str),
                    backup_topic_id=entry["backup_id"],
                    name=entry["name"],
                ))
        return cls(
            id=obj.id,
            main_channel_id=obj.main_channel_id,
            backup_channel_id=obj.backup_channel_id,
            title=obj.title,
            is_active=obj.is_active,
            is_promoted=obj.is_promoted,
            synced_count=obj.synced_count,
            last_sync_at=obj.last_sync_at.isoformat() if obj.last_sync_at else None,
            failure_count=obj.failure_count,
            max_failures=obj.max_failures,
            last_failure_at=obj.last_failure_at.isoformat() if obj.last_failure_at else None,
            topics=topics,
        )


@router.get("/channels", response_model=list[BackupChannelOut])
async def list_backups(session: DBSession, _admin=Depends(get_admin_user)) -> list[BackupChannelOut]:
    """List all configured backup channels."""
    result = await session.execute(select(BackupChannel).order_by(BackupChannel.id))
    return [BackupChannelOut.from_orm(b) for b in result.scalars().all()]


@router.post("/channels", response_model=BackupChannelOut)
async def create_backup(
    body: CreateBackupRequest,
    session: DBSession,
    _admin=Depends(get_admin_user),
) -> BackupChannelOut:
    """
    Create a backup channel for a main Telegram channel.
    Optionally invites all current members of the main channel.
    Message sync must be triggered separately.
    """
    worker_result = await worker_manager.get_best_worker(session)
    if not worker_result:
        raise HTTPException(503, "No workers available")
    _, client = worker_result

    try:
        backup = await backup_service.create_backup_channel(
            session, client, body.main_channel_id, body.title
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if body.invite_members:
        try:
            invited = await backup_service.invite_members(
                client, body.main_channel_id, backup.backup_channel_id
            )
            logger.info(f"Invited {invited} members to backup channel {backup.id}")
        except Exception as e:
            logger.warning(f"Member invitation partially failed: {e}")

    # Always promote main-channel admins to admin in the backup
    try:
        promoted = await backup_service.promote_admins(
            client, body.main_channel_id, backup.backup_channel_id
        )
        logger.info(f"Promoted {promoted} admins in backup channel {backup.id}")
    except Exception as e:
        logger.warning(f"Admin promotion partially failed: {e}")

    # Auto-sync messages immediately after creation
    try:
        synced = await backup_service.sync_messages(session, client, backup)
        logger.info(f"Auto-synced {synced} messages for backup channel {backup.id}")
    except Exception as e:
        logger.warning(f"Auto-sync partially failed: {e}")

    return BackupChannelOut.from_orm(backup)


@router.post("/channels/{backup_id}/sync")
async def sync_backup(
    backup_id: int,
    session: DBSession,
    _admin=Depends(get_admin_user),
) -> dict:
    """Trigger a message sync for a specific backup channel."""
    result = await session.execute(
        select(BackupChannel).where(BackupChannel.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(404, "Backup channel not found")

    worker_result = await worker_manager.get_best_worker(session)
    if not worker_result:
        raise HTTPException(503, "No workers available")
    _, client = worker_result

    synced = await backup_service.sync_messages(session, client, backup)
    return {"synced": synced, "total": backup.synced_count}


@router.patch("/channels/{backup_id}/toggle")
async def toggle_backup(
    backup_id: int,
    session: DBSession,
    _admin=Depends(get_admin_user),
) -> BackupChannelOut:
    """Enable or disable a backup channel as fallback."""
    result = await session.execute(
        select(BackupChannel).where(BackupChannel.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(404, "Backup channel not found")

    backup.is_active = not backup.is_active
    await session.commit()
    return BackupChannelOut.from_orm(backup)


@router.post("/channels/{backup_id}/promote", response_model=BackupChannelOut)
async def promote_backup(
    backup_id: int,
    session: DBSession,
    _admin=Depends(get_admin_user),
) -> BackupChannelOut:
    """Manually promote backup to main, redirect MediaParts, create new backup."""
    result = await session.execute(
        select(BackupChannel).where(BackupChannel.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(404, "Backup channel not found")
    if backup.is_promoted:
        raise HTTPException(400, "Already promoted")

    worker_result = await worker_manager.get_best_worker(session)
    if not worker_result:
        raise HTTPException(503, "No workers available")
    _, client = worker_result

    new_backup = await backup_service.promote_to_main(session, client, backup)
    return BackupChannelOut.from_orm(new_backup)


@router.patch("/channels/{backup_id}/max-failures")
async def set_max_failures(
    backup_id: int,
    max_failures: int,
    session: DBSession,
    _admin=Depends(get_admin_user),
) -> BackupChannelOut:
    """Update the failure threshold before auto-promotion."""
    result = await session.execute(
        select(BackupChannel).where(BackupChannel.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(404, "Backup channel not found")
    if max_failures < 1:
        raise HTTPException(400, "max_failures must be >= 1")
    backup.max_failures = max_failures
    await session.commit()
    return BackupChannelOut.from_orm(backup)


@router.delete("/channels/{backup_id}", status_code=204)
async def delete_backup(
    backup_id: int,
    session: DBSession,
    _admin=Depends(get_admin_user),
    delete_telegram: bool = False,
) -> None:
    """Remove backup config from DB. Pass ?delete_telegram=true to also delete the Telegram supergroup."""
    result = await session.execute(
        select(BackupChannel).where(BackupChannel.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(404, "Backup channel not found")

    backup_tg_id = backup.backup_channel_id
    await session.delete(backup)
    await session.commit()

    if delete_telegram:
        try:
            worker_result = await worker_manager.get_best_worker(session)
            if worker_result:
                _, client = worker_result
                await backup_service.delete_telegram_group(client, backup_tg_id)
        except Exception as e:
            logger.warning(f"[BACKUP] Could not delete Telegram group {backup_tg_id}: {e}")
