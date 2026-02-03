"""Scanner schemas."""

from pydantic import BaseModel


class ScanRequest(BaseModel):
    """Request model for scan endpoint."""

    limit: int = 100
    topic_id: int | None = None


class ScanResponse(BaseModel):
    """Response model for scan endpoint."""

    channels: int = 0
    topics: int = 0
    files_found: int = 0
    media_created: int = 0
    errors: list[str] = []


class ScanStatusResponse(BaseModel):
    """Response model for scan status."""

    is_scanning: bool
