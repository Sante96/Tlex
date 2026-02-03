"""Loguru configuration for the application."""

import json
import logging
import sys

from loguru import logger

from app.config import get_settings


def json_serializer(record: dict) -> str:
    """Serialize log record to JSON for structured logging."""
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }

    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else None,
            "value": str(record["exception"].value) if record["exception"].value else None,
        }

    # Add extra fields if present
    if record["extra"]:
        log_entry["extra"] = record["extra"]

    return json.dumps(log_entry, default=str)


def json_sink(message):
    """Sink function for JSON output."""
    record = message.record
    print(json_serializer(record), file=sys.stderr)


def setup_logging() -> None:
    """Configure loguru for the application."""
    settings = get_settings()

    # Remove default handler
    logger.remove()

    if settings.environment == "dev":
        # Development: colored console output
        log_format = (
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        log_level = "DEBUG" if settings.debug else "INFO"

        logger.add(
            sys.stderr,
            format=log_format,
            level=log_level,
            colorize=True,
        )
    else:
        # Production: JSON structured logging
        log_level = "INFO"

        logger.add(
            json_sink,
            level=log_level,
            format="{message}",
        )

        # File handler with JSON
        logger.add(
            "logs/tlex_{time:YYYY-MM-DD}.json",
            rotation="00:00",
            retention="30 days",
            compression="gz",
            serialize=True,
            level="INFO",
        )

    # Silence noisy loggers
    for noisy_logger in [
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "httpx",
        "httpcore",
        "pyrogram",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logger.info(f"Logging configured for {settings.environment} environment")
