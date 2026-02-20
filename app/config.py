"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================
    # Environment
    # ============================================
    environment: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False
    enable_registration: bool = True

    # ============================================
    # Telegram API
    # ============================================
    api_id: int
    api_hash: str

    # ============================================
    # Database (PostgreSQL)
    # ============================================
    postgres_user: str = "tlex"
    postgres_password: str = "tlex_secret"
    postgres_db: str = "tlex_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        """Build async database URL for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ============================================
    # Redis
    # ============================================
    redis_host: str = "localhost"
    redis_port: int = 6379

    @property
    def redis_url(self) -> str:
        """Build Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # ============================================
    # Security (JWT)
    # ============================================
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30  # 30 minutes for access token
    jwt_refresh_expire_days: int = 30  # 30 days for refresh token

    # CORS
    cors_allowed_origins: str = "http://localhost:3000"  # Comma-separated origins

    # ============================================
    # TMDB API
    # ============================================
    tmdb_api_key: str = ""
    tmdb_language: str = "it-IT"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p"

    # ============================================
    # Application
    # ============================================
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Worker Pool Settings
    max_workers_standard: int = 1
    max_workers_premium: int = 10
    chunk_size_bytes: int = 1048576  # 1MB

    # ============================================
    # Scanner Settings
    # ============================================
    scanner_channel_ids: str = ""  # Comma-separated channel IDs
    scanner_video_extensions: str = ".mkv,.mp4,.avi,.webm"
    scanner_split_extensions: str = ".001,.002,.003"
    scanner_movies_topic_id: int | None = None  # Topic ID for Movies Archive (bucket strategy)
    scanner_auto_interval_hours: int = 0  # Auto-scan interval in hours (0 = disabled)

    @property
    def channel_ids_list(self) -> list[int]:
        """Parse comma-separated channel IDs."""
        if not self.scanner_channel_ids:
            return []
        return [int(cid.strip()) for cid in self.scanner_channel_ids.split(",") if cid.strip()]

    @property
    def video_extensions_list(self) -> list[str]:
        """Parse video extensions."""
        return [ext.strip().lower() for ext in self.scanner_video_extensions.split(",")]

    @property
    def split_extensions_list(self) -> list[str]:
        """Parse split file extensions."""
        return [ext.strip().lower() for ext in self.scanner_split_extensions.split(",")]

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        if not self.cors_allowed_origins:
            return []
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
