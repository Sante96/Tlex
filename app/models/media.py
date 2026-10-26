"""Media models for the virtual file system."""

import enum
from datetime import date

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MediaType(str, enum.Enum):
    """Type of media item."""

    MOVIE = "MOVIE"
    EPISODE = "EPISODE"
    CONCERT = "CONCERT"


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
    season_posters: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {season_num: poster_path}

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


class Franchise(Base):
    """The anime or game a "Concerti · <name>" topic holds the concerts of.

    Its own table, not a Series: the anime may also be in the library as a series, with
    the same TMDB id (Series.tmdb_id is unique), and concerts must stay out of Series.
    """

    __tablename__ = "franchises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # The topic's name, normalized: how scans find it again, whatever the title becomes
    key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    concerts: Mapped[list["MediaItem"]] = relationship("MediaItem", back_populates="franchise")

    def __repr__(self) -> str:
        return f"<Franchise(id={self.id}, title={self.title})>"


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
    # Where the credits start, set by hand in the player: Up next shows from there, and the
    # title counts as watched (app/services/credits.py: when unset)
    credits_start_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Video keyframe times for precise seeking (JSON array of seconds). Replaced the
    # keyframes_index column, whose lists also held subtitle cue times. Deferred: tens of
    # KB that every list page, series page and progress save loaded for nothing
    video_keyframes: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    content_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vote_average: Mapped[float | None] = mapped_column(nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated

    # Chapters from the file ([{"start", "end", "title"}], the seekbar's segments). NULL:
    # never probed (app/services/chapters.py fills those in); [] : the file has none.
    # Deferred like video_keyframes: only the details need them
    chapters: Mapped[list | None] = mapped_column(
        JSON(none_as_null=True), nullable=True, deferred=True
    )

    # For concerts: their anime/game, and the song titles of the chapters (one per chapter,
    # None for an untitled one). Its own column: "Analizza" rewrites chapters, not this
    franchise_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("franchises.id", ondelete="SET NULL"), nullable=True, index=True
    )
    setlist: Mapped[list | None] = mapped_column(
        JSON(none_as_null=True), nullable=True, deferred=True
    )

    # For episodes - link to series
    series_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=True, index=True
    )
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    series: Mapped["Series | None"] = relationship("Series", back_populates="episodes")
    franchise: Mapped["Franchise | None"] = relationship("Franchise", back_populates="concerts")
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
    # The scanner looks parts up by their Telegram message, the failover by channel
    __table_args__ = (Index("ix_media_parts_channel_message", "channel_id", "message_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False, index=True
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
        Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False, index=True
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
