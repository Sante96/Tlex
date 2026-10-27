"""Backup channel models."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ArchiveAccount(Base):
    """A Telegram account kept out of streaming: it owns an archive group (a backup no
    worker is in) and goes online once a day to fill it, so a ban of the workers, who
    make thousands of requests a day, can't take it down with them."""

    __tablename__ = "archive_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    session_string: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BackupChannel(Base):
    """A backup Telegram channel mirroring a main channel."""

    __tablename__ = "backup_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    main_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    backup_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    synced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topic_map: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )  # {str(main_topic_id): backup_topic_id}
    # Health / failover
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_failures: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_promoted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # An archive group: its account fills it, never promoted on its own, no stream fallback.
    # Not SET NULL: the account's removal would turn its group into a workers' backup
    archive_account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("archive_accounts.id"), nullable=True
    )

    messages: Mapped[list["BackupMessage"]] = relationship(
        "BackupMessage", back_populates="backup_channel", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BackupChannel(id={self.id}, main={self.main_channel_id}, backup={self.backup_channel_id})>"


class BackupMessage(Base):
    """Maps a main channel message to its forwarded counterpart in a backup channel."""

    __tablename__ = "backup_messages"
    __table_args__ = (
        UniqueConstraint("backup_channel_db_id", "main_message_id", name="uq_backup_msg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backup_channel_db_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backup_channels.id", ondelete="CASCADE"), nullable=False
    )
    main_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    main_message_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    backup_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # The main message moved (a corrected download): an archive's own account deletes this
    # copy at its daily run, since no worker is in that group
    pending_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    backup_channel: Mapped["BackupChannel"] = relationship(
        "BackupChannel", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<BackupMessage(main_msg={self.main_message_id} -> backup_msg={self.backup_message_id})>"
