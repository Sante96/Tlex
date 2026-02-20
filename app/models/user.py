"""User and Profile models."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if False:  # TYPE_CHECKING
    from app.models.worker import Worker


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    profiles: Mapped[list["Profile"]] = relationship(
        "Profile", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Profile(Base):
    """User profile model (Netflix-style multi-profile support)."""

    __tablename__ = "profiles"
    __table_args__ = (
        UniqueConstraint("worker_id", name="uq_profile_worker"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    worker_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workers.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_kids: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferences: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "default_audio": "ita",
            "default_subtitle": "ita",
            "subtitles_enabled": True,
            "autoplay_next": True,
        },
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profiles")
    worker: Mapped["Worker | None"] = relationship("Worker", lazy="joined")

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, name={self.name})>"


class RefreshToken(Base):
    """Refresh token model for JWT token refresh."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"


class Watchlist(Base):
    """User's watchlist/favorites – supports both media items and series."""

    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "media_item_id", name="uq_watchlist_user_media"),
        UniqueConstraint("user_id", "series_id", name="uq_watchlist_user_series"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=True
    )
    series_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Watchlist(user={self.user_id}, media={self.media_item_id}, series={self.series_id})>"


class WatchProgress(Base):
    """Track user's watch progress for Continue Watching feature."""

    __tablename__ = "watch_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    media_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False
    )
    position_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<WatchProgress(user={self.user_id}, media={self.media_item_id}, pos={self.position_seconds})>"

    @property
    def progress_percent(self) -> float:
        """Calculate watch progress as percentage."""
        if self.duration_seconds == 0:
            return 0.0
        return min(100.0, (self.position_seconds / self.duration_seconds) * 100)


class UserMediaOverride(Base):
    """Per-user visual overrides for media items (poster, backdrop, etc.)."""

    __tablename__ = "user_media_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "media_item_id", name="uq_user_media_override"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False
    )
    poster_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<UserMediaOverride(user={self.user_id}, media={self.media_item_id})>"


class UserSeriesOverride(Base):
    """Per-user visual overrides for TV series (poster, backdrop, season posters)."""

    __tablename__ = "user_series_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "series_id", name="uq_user_series_override"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=False
    )
    poster_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    season_posters: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<UserSeriesOverride(user={self.user_id}, series={self.series_id})>"
