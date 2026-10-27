"""The Download page (every logged-in user) and the seedbox agent's sync."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import defer

from app.api.deps import DBSession
from app.config import get_settings
from app.models.download import Download, DownloadKind, DownloadStatus
from app.schemas.download import (
    AgentCommands,
    AgentSync,
    DownloadOut,
    DownloadsResponse,
    DownloadUpdate,
    SeedboxStatus,
    TorrentPreview,
)
from app.services.downloads import move, service

MAX_TORRENT_BYTES = 10 * 1024 * 1024


async def _agent_token(x_agent_token: Annotated[str, Header()] = "") -> None:
    expected = get_settings().seedbox_agent_token
    if not expected:  # no agent set up: these endpoints don't exist
        raise HTTPException(status_code=404)
    if not hmac.compare_digest(x_agent_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid agent token")


router = APIRouter()  # mounted behind the login
agent_router = APIRouter(dependencies=[Depends(_agent_token)])


async def _read(torrent: UploadFile | None) -> bytes | None:
    if torrent is None:
        return None
    data = await torrent.read(MAX_TORRENT_BYTES + 1)
    if len(data) > MAX_TORRENT_BYTES:
        raise HTTPException(status_code=400, detail="The .torrent file is too big")
    return data or None


async def _download(session: DBSession, download_id: int) -> Download:
    # Locked: the agent's sync and a move write the same row
    query = select(Download).where(Download.id == download_id).with_for_update()
    download = await session.scalar(query)
    if download is None:
        raise HTTPException(status_code=404, detail="Download not found")
    return download


@router.get("", response_model=DownloadsResponse)
async def list_downloads(session: DBSession) -> DownloadsResponse:
    # Polled every 3 s: the .torrent files (the page never shows them) stay in the database
    query = select(Download).options(defer(Download.torrent)).order_by(Download.id.desc())
    rows = await session.scalars(query)
    return DownloadsResponse(
        seedbox=SeedboxStatus(**service.seedbox_status()),
        downloads=[DownloadOut.model_validate(d) for d in rows],
    )


@router.post("/preview", response_model=TorrentPreview)
async def preview_torrent(
    magnet: Annotated[str | None, Form()] = None,
    torrent: Annotated[UploadFile | None, File()] = None,
) -> TorrentPreview:
    """The torrent's name, and the name and season the form starts from."""
    return TorrentPreview(**service.preview(magnet, await _read(torrent)))


@router.post("", status_code=201, response_model=DownloadOut)
async def add_download(
    session: DBSession,
    kind: Annotated[DownloadKind, Form()],
    magnet: Annotated[str | None, Form()] = None,
    torrent: Annotated[UploadFile | None, File()] = None,
    name: Annotated[str | None, Form()] = None,
    season: Annotated[int | None, Form()] = None,
) -> DownloadOut:
    try:
        download = await service.add_download(
            session,
            kind=kind,
            magnet=magnet,
            torrent=await _read(torrent),
            name=name,
            season=season,
        )
    except service.AlreadyQueued:
        raise HTTPException(status_code=409, detail="Already downloading") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return DownloadOut.model_validate(download)


@router.patch("/{download_id}", response_model=DownloadOut)
async def update_download(download_id: int, body: DownloadUpdate, session: DBSession):
    download = await _download(session, download_id)
    try:
        service.set_destination(download, body.kind, body.name, body.season)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    await session.commit()
    # Files on Telegram follow the correction, in the background: the move checks each
    # one's topic on Telegram, so saving again also finishes a move that failed
    if any(f["uploaded"] for f in download.files):
        move.schedule_move(download.id)
    return DownloadOut.model_validate(download)


async def _command(session: DBSession, download_id: int, action: str, paused: bool) -> None:
    download = await _download(session, download_id)
    if download.status in (DownloadStatus.removing, DownloadStatus.library):
        raise HTTPException(status_code=409, detail="Already removed from the seedbox")
    download.action, download.paused = action, paused
    await session.commit()


@router.post("/{download_id}/pause", status_code=204)
async def pause_download(download_id: int, session: DBSession) -> None:
    await _command(session, download_id, "pause", paused=True)


@router.post("/{download_id}/resume", status_code=204)
async def resume_download(download_id: int, session: DBSession) -> None:
    await _command(session, download_id, "resume", paused=False)


@router.delete("/{download_id}", status_code=204)
async def remove_download(download_id: int, session: DBSession) -> None:
    await service.remove_download(session, await _download(session, download_id))


@agent_router.post("/sync", response_model=AgentCommands)
async def agent_sync(report: AgentSync, session: DBSession) -> AgentCommands:
    """The seedbox agent, every 3 s: its state in, the commands out."""
    return await service.handle_sync(session, report)
