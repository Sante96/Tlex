"""A torrent the seedbox downloads and uploads into Telegram."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DownloadKind(StrEnum):
    film = "film"
    series = "series"
    anime = "anime"
    concert = "concert"


class DownloadStatus(StrEnum):
    queued = "queued"
    downloading = "downloading"
    uploading = "uploading"
    scanning = "scanning"
    removing = "removing"
    library = "library"
    error = "error"


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(500))
    season: Mapped[int | None] = mapped_column(Integer)
    magnet: Mapped[str | None] = mapped_column(Text)
    torrent: Mapped[bytes | None] = mapped_column(LargeBinary)
    torrent_name: Mapped[str | None] = mapped_column(String(500))
    info_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=DownloadStatus.queued.value, nullable=False
    )
    paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # The command waiting for the agent: pause, resume or remove.
    action: Mapped[str | None] = mapped_column(String(20))
    # The "add" command has already been handed to the agent.
    sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # [{"path", "size", "topic", "topic_id", "progress", "message_ids", "uploaded"}]
    files: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    live: Mapped[dict | None] = mapped_column(JSON)
    upload: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
