"""Telegram Worker model for the account pool."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkerStatus(str, enum.Enum):
    """Worker status enum."""

    ACTIVE = "ACTIVE"
    FLOOD_WAIT = "FLOOD_WAIT"
    OFFLINE = "OFFLINE"


class Worker(Base):
    """Telegram worker account for the connection pool."""

    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_string: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_concurrent_streams: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_load: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[WorkerStatus] = mapped_column(
        Enum(WorkerStatus), default=WorkerStatus.OFFLINE, nullable=False
    )
    flood_wait_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Worker(id={self.id}, phone={self.phone_number}, status={self.status.value})>"

    @property
    def is_available(self) -> bool:
        """Check if worker can accept new streams."""
        if self.status != WorkerStatus.ACTIVE:
            return False
        return self.current_load < self.max_concurrent_streams

    @property
    def available_slots(self) -> int:
        """Number of available stream slots."""
        if self.status != WorkerStatus.ACTIVE:
            return 0
        return max(0, self.max_concurrent_streams - self.current_load)
