"""Media models for the virtual file system."""

import enum
from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MediaType(str, enum.Enum):
    """Type of media item."""

    MOVIE = "MOVIE"
    EPISODE = "EPISODE"


class CodecType(str, enum.Enum):
    """Type of media stream codec."""

    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    SUBTITLE = "SUBTITLE"


class Series(Base):
    """TV Series entity - groups seasons and episodes."""

    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # New fields for extended metadata
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    vote_average: Mapped[float | None] = mapped_column(nullable=True)  # TMDB rating 0-10
    content_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. "TV-MA"

    # Relationships
    episodes: Mapped[list["MediaItem"]] = relationship(
        "MediaItem", back_populates="series", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Series(id={self.id}, title={self.title})>"

    @property
    def seasons(self) -> list[int]:
        """Get unique season numbers."""
        return sorted({ep.season_number for ep in self.episodes if ep.season_number})

    @property
    def seasons_count(self) -> int:
        """Count unique seasons."""
        return len(self.seasons)

    @property
    def episodes_count(self) -> int:
        """Total episodes count."""
        return len(self.episodes)


class MediaItem(Base):
    """The movie or episode entity."""

    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType), default=MediaType.MOVIE, nullable=False
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Keyframe index for precise seeking (JSON array of timestamps in seconds)
    keyframes_index: Mapped[str | None] = mapped_column(Text, nullable=True)

    # For episodes - link to series
    series_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=True
    )
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    series: Mapped["Series | None"] = relationship("Series", back_populates="episodes")
    parts: Mapped[list["MediaPart"]] = relationship(
        "MediaPart", back_populates="media_item", cascade="all, delete-orphan"
    )
    streams: Mapped[list["MediaStream"]] = relationship(
        "MediaStream", back_populates="media_item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MediaItem(id={self.id}, title={self.title})>"

    @property
    def total_size(self) -> int:
        """Calculate total file size from all parts."""
        return sum(part.file_size for part in self.parts)


class MediaPart(Base):
    """Virtual file system - handles split files (>4GB)."""

    __tablename__ = "media_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False
    )
    telegram_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    part_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0, 1, 2...
    start_byte: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Global offset start
    end_byte: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Global offset end
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Telegram location coordinates (for downloading)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # message_thread_id
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    media_item: Mapped["MediaItem"] = relationship("MediaItem", back_populates="parts")

    def __repr__(self) -> str:
        return f"<MediaPart(id={self.id}, part_index={self.part_index}, size={self.file_size})>"

    def contains_byte(self, byte_offset: int) -> bool:
        """Check if this part contains the given byte offset."""
        return self.start_byte <= byte_offset < self.end_byte

    def local_offset(self, global_offset: int) -> int:
        """Convert global byte offset to local offset within this part."""
        return global_offset - self.start_byte


class MediaStream(Base):
    """Technical metadata for video/audio/subtitle tracks."""

    __tablename__ = "media_streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False
    )
    stream_index: Mapped[int] = mapped_column(Integer, nullable=False)  # FFmpeg index
    codec_type: Mapped[CodecType] = mapped_column(Enum(CodecType), nullable=False)
    codec_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., h264, aac, ass
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO code
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Track title
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    media_item: Mapped["MediaItem"] = relationship("MediaItem", back_populates="streams")

    def __repr__(self) -> str:
        return f"<MediaStream(id={self.id}, type={self.codec_type.value}, codec={self.codec_name})>"
