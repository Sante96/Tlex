"""Scanner API endpoints for media ingestion."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DBSession, get_admin_user
from app.schemas import ScanRequest, ScanResponse, ScanStatusResponse
from app.services.scanner import scanner_service

router = APIRouter()


@router.post("/scan", response_model=ScanResponse)
async def trigger_scan(
    request: ScanRequest,
    session: DBSession,
    _admin=Depends(get_admin_user),
) -> ScanResponse:
    """
    Trigger a scan of configured Telegram channels.

    This will:
    1. Scan all channels configured in SCANNER_CHANNEL_IDS
    2. Detect video files and split parts
    3. Group split files into single media items
    4. Fetch metadata from TMDB
    5. Store in database
    """
    if scanner_service.is_scanning:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    result = await scanner_service.scan_all_channels(session, limit=request.limit, topic_id=request.topic_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return ScanResponse(**result)


@router.get("/status", response_model=ScanStatusResponse)
async def get_scan_status() -> ScanStatusResponse:
    """Get current scan status."""
    return ScanStatusResponse(is_scanning=scanner_service.is_scanning)
