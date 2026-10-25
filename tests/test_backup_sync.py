"""BackupService.sync_all must give its pool client back (it used to leak one per run)."""

from unittest.mock import AsyncMock, MagicMock

from app.services.backup import backup_service


async def test_sync_all_releases_client_even_when_a_backup_fails(mocker):
    client = MagicMock()
    session = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [MagicMock(id=1)]
    maker = mocker.patch("app.services.backup._sync_mixin.async_session_maker")
    maker.return_value.__aenter__.return_value = session
    mocker.patch(
        "app.core.worker_manager.worker_manager.get_available_clients",
        new=AsyncMock(return_value=[client]),
    )
    release = mocker.patch("app.core.worker_manager.worker_manager.release_clients")
    mocker.patch.object(backup_service, "check_health", new=AsyncMock(side_effect=RuntimeError))

    result = await backup_service.sync_all()

    assert result["errors"]
    release.assert_called_once_with([client])


async def test_sync_all_without_backups_takes_no_client(mocker):
    session = AsyncMock()
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    maker = mocker.patch("app.services.backup._sync_mixin.async_session_maker")
    maker.return_value.__aenter__.return_value = session
    acquire = mocker.patch(
        "app.core.worker_manager.worker_manager.get_available_clients", new=AsyncMock()
    )

    await backup_service.sync_all()

    acquire.assert_not_called()
