"""Backup channel service — assembled from domain mixins."""

from app.services.backup._members_mixin import BackupMembersMixin
from app.services.backup._sync_mixin import BackupSyncMixin


# BackupSyncMixin brings BackupFailoverMixin, which brings BackupCreateMixin
class BackupService(BackupSyncMixin, BackupMembersMixin):
    """
    Manages backup Telegram channels.

    Responsibilities:
    - Create a megagroup with forum topics mirroring the main channel
    - Invite members and promote admins
    - Forward messages per-topic preserving topic structure
    - Store main_message_id → backup_message_id mappings
    - Health checks and automatic failover promotion
    - Fallback file_id retrieval when main channel is unavailable
    """


# Singleton
backup_service = BackupService()
