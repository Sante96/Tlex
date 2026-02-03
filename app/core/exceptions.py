"""Custom exceptions and error handling for TLEX."""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger


class TLEXException(Exception):
    """Base exception for TLEX application."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)


class NotFoundError(TLEXException):
    """Resource not found."""

    def __init__(self, resource: str, resource_id: int | str | None = None):
        msg = f"{resource} not found"
        if resource_id:
            msg = f"{resource} with id {resource_id} not found"
        super().__init__(msg, status_code=status.HTTP_404_NOT_FOUND)


class UnauthorizedError(TLEXException):
    """Authentication required or failed."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(TLEXException):
    """Permission denied."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class BadRequestError(TLEXException):
    """Invalid request data."""

    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)


class ConflictError(TLEXException):
    """Resource conflict (e.g., duplicate)."""

    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class ServiceUnavailableError(TLEXException):
    """External service unavailable."""

    def __init__(self, service: str, message: str | None = None):
        msg = f"{service} is unavailable"
        if message:
            msg = f"{msg}: {message}"
        super().__init__(msg, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class WorkerUnavailableError(ServiceUnavailableError):
    """No Telegram workers available."""

    def __init__(self):
        super().__init__("Telegram workers", "No workers available for streaming")


async def tlex_exception_handler(request: Request, exc: TLEXException) -> JSONResponse:
    """Global exception handler for TLEXException."""
    logger.warning(f"TLEXException: {exc.message} (status={exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global handler for unhandled exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": str(exc) if request.app.debug else None,
        },
    )
