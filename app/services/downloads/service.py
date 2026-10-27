"""Downloads: what the page adds, what the seedbox agent reports, and the commands back."""

import asyncio
import base64
import time
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.download import Download, DownloadKind, DownloadStatus
from app.models.media import Franchise, Series
from app.schemas.download import AgentAdd, AgentCommands, AgentPlan, AgentPlanFile, AgentSync
from app.services.downloads.plan import (
    destination_topic,
    file_topic,
    guess,
    info_hash,
    torrent_name,
    uploadable,
)
from app.services.scanner.service import scanner_service

OFFLINE_AFTER = 30  # seconds without a sync: the page shows the seedbox as not connected
SCAN_RETRY_SECONDS = 30  # the scanner is busy (auto-scan, another download): wait, try again
SCAN_RETRIES = 20
NO_VIDEOS = "Nessun video da caricare"
ALREADY_DOWNLOADING = "Già in download"

_TRANSFERRING = (DownloadStatus.downloading, DownloadStatus.uploading)
# The agent has nothing more to do with these until the user acts
_ENDED = (DownloadStatus.removing, DownloadStatus.library, DownloadStatus.error)

# One backend process: the seedbox's last sync lives here, not in the database
_seedbox: dict = {"last_seen": None, "free_bytes": None, "dl_speed": None, "up_speed": None}
# The running scans, by download: a "scanning" row without one lost it in a restart
_tasks: dict[asyncio.Task, int] = {}


class AlreadyQueued(Exception):
    """A download that is not in the library yet has this magnet's hash."""


def seedbox_status(now: float | None = None) -> dict:
    now = time.time() if now is None else now
    last_seen = _seedbox["last_seen"]
    return {**_seedbox, "connected": last_seen is not None and now - last_seen < OFFLINE_AFTER}


def preview(magnet: str | None, torrent: bytes | None) -> dict:
    # A .torrent file, when there is one, is what gets added (see add_download)
    name = torrent_name(None if torrent else magnet, torrent)
    return {"torrent_name": name, **(guess(name) if name else {"name": None, "season": None})}


async def add_download(
    session: AsyncSession,
    *,
    kind: DownloadKind,
    magnet: str | None,
    torrent: bytes | None,
    name: str | None,
    season: int | None,
) -> Download:
    """ValueError for what the form got wrong, AlreadyQueued for a magnet already here."""
    magnet = None if torrent else (magnet or "").strip() or None
    name = (name or "").strip() or None
    if not magnet and not torrent:
        raise ValueError("A magnet or a .torrent file is required")
    found = torrent_name(magnet, torrent)
    if torrent and found is None:
        raise ValueError("The .torrent file is not valid")
    destination_topic(kind, name, season)  # raises without a name, but for a film
    # A .torrent's hash is known once the agent reports it (handle_sync checks it there)
    hash_ = info_hash(magnet) if magnet else None
    if hash_ and await session.scalar(
        select(Download.id)
        .where(Download.info_hash == hash_, Download.status != DownloadStatus.library)
        .limit(1)
    ):
        raise AlreadyQueued
    download = Download(
        kind=kind,
        name=name,
        season=season,
        magnet=magnet,
        torrent=torrent,
        torrent_name=found,
        info_hash=hash_,
        files=[],
    )
    session.add(download)
    await session.commit()
    return download


def set_destination(
    download: Download, kind: DownloadKind, name: str | None, season: int | None
) -> None:
    """A correction from the page: each file's topic follows it (the caller commits)."""
    name = (name or "").strip() or None
    destination_topic(kind, name, season)
    download.kind, download.name, download.season = kind, name, season
    download.files = [
        {**f, "topic": file_topic(kind, name, season, f["path"])} for f in download.files
    ]


async def remove_download(session: AsyncSession, download: Download) -> None:
    """Off the seedbox, and nothing else: what is in the library stays. The agent deletes
    the parts of a file it left half uploaded (it alone knows their ids)."""
    # Midway, the files already on Telegram still reach the library
    midway = download.status in (*_TRANSFERRING, DownloadStatus.error)
    topic_ids = sorted({f["topic_id"] for f in download.files if f["uploaded"]})
    download.action, download.status, download.upload = "remove", DownloadStatus.removing, None
    await session.commit()
    if midway and topic_ids:
        schedule_scan(download.id, topic_ids)


def _plan_files(download: Download, files: list) -> None:
    """The torrent's file list has arrived: the videos to upload and their topics."""
    kind = DownloadKind(download.kind)
    download.files = [
        {
            "path": f.path,
            "size": f.size,
            "topic": file_topic(kind, download.name, download.season, f.path),
            "topic_id": None,
            "progress": f.progress,
            "message_ids": [],
            "uploaded": False,
        }
        for f in files
        if uploadable(f.path)
    ]
    if download.files:
        download.status = DownloadStatus.downloading
    else:
        download.status, download.error = DownloadStatus.error, NO_VIDEOS


async def handle_sync(session: AsyncSession, report: AgentSync) -> AgentCommands:
    """The agent's report every 3 s: record it, move the downloads on, answer with commands."""
    _seedbox.update(
        last_seen=time.time(),
        free_bytes=report.free_bytes,
        dl_speed=report.dl_speed,
        up_speed=report.up_speed,
    )
    # The library's history is not the agent's business. Locked: a correction and a move
    # write the same files lists
    rows = await session.scalars(
        select(Download).where(Download.status != DownloadStatus.library).with_for_update()
    )
    downloads = {d.id: d for d in rows}

    for t in report.torrents:
        d = downloads.get(t.download_id)
        if d is None or d.status in _ENDED:
            continue
        hash_ = t.hash.lower()
        if d.info_hash != hash_:
            # A second .torrent of something already downloading (a magnet got a 409)
            if any(o is not d and o.info_hash == hash_ for o in downloads.values()):
                d.status, d.error = DownloadStatus.error, ALREADY_DOWNLOADING
                continue
            d.info_hash = hash_
        d.live = t.model_dump(exclude={"download_id", "files"})
        if not d.files:
            if t.files:  # a magnet has none until its metadata arrives
                _plan_files(d, t.files)
        else:
            progress = {f.path: f.progress for f in t.files}
            d.files = [{**f, "progress": progress.get(f["path"], f["progress"])} for f in d.files]

    to_move: set[int] = set()
    for u in report.uploads:
        if (d := downloads.get(u.download_id)) is None:
            continue
        # Only once: a later move changes the ids, a repeated report must not
        f = next((f for f in d.files if f["path"] == u.path and not f["uploaded"]), None)
        if f is None:
            continue
        d.files = [
            {**g, "uploaded": True, "topic_id": u.topic_id, "message_ids": u.message_ids}
            if g is f
            else g
            for g in d.files
        ]
        if u.topic is not None and u.topic != f["topic"]:
            to_move.add(d.id)  # corrected during its upload: it went to the old topic

    current = report.current_upload
    to_scan: list[Download] = []
    for d in downloads.values():
        if d.status == DownloadStatus.scanning and d.id not in _tasks.values():
            to_scan.append(d)  # its scan task ended with the backend's last run
            continue
        if d.status not in _TRANSFERRING:
            continue
        if all(f["uploaded"] for f in d.files):
            d.status, d.upload = DownloadStatus.scanning, None
            to_scan.append(d)
        elif current is not None and current.download_id == d.id:
            d.status = DownloadStatus.uploading
            d.upload = current.model_dump(exclude={"download_id"})
        else:
            d.status, d.upload = DownloadStatus.downloading, None

    for download_id in report.removed:
        d = downloads.pop(download_id, None)
        if d is None:
            continue
        # finished_at: it was already in the library (a Remove on its card); all uploaded:
        # the removal after the scan. Otherwise a Remove midway: nothing to keep.
        if d.finished_at is not None or (d.files and all(f["uploaded"] for f in d.files)):
            d.status = DownloadStatus.library
            d.finished_at = d.finished_at or datetime.now(UTC).replace(tzinfo=None)
        else:
            await session.delete(d)

    for e in report.errors:
        if d := downloads.get(e.download_id):
            d.status, d.error = DownloadStatus.error, e.error

    commands = AgentCommands()
    for d in downloads.values():
        if not d.sent and d.status == DownloadStatus.queued:
            torrent_b64 = base64.b64encode(d.torrent).decode() if d.torrent else None
            commands.add.append(
                AgentAdd(download_id=d.id, magnet=d.magnet, torrent_b64=torrent_b64)
            )
            d.sent = True
        if d.action:
            getattr(commands, d.action).append(d.id)  # "pause", "resume" or "remove"
            d.action = None
        pending = [
            AgentPlanFile(path=f["path"], topic=f["topic"]) for f in d.files if not f["uploaded"]
        ]
        if pending and d.status in _TRANSFERRING:
            commands.plans.append(AgentPlan(download_id=d.id, files=pending))
    await session.commit()

    for d in to_scan:
        schedule_scan(d.id, sorted({f["topic_id"] for f in d.files}))
    if to_move:
        from app.services.downloads.move import schedule_move  # move.py imports this module

        for download_id in to_move:
            schedule_move(download_id)
    return commands


async def _scan(topic_id: int) -> None:
    for _ in range(SCAN_RETRIES):
        async with async_session_maker() as session:
            result = await scanner_service.scan_all_channels(session, topic_id=topic_id)
        if result.get("error") != "Scan already in progress":
            if "error" in result:
                logger.warning(f"Scan of topic {topic_id}: {result['error']}")
            return
        await asyncio.sleep(SCAN_RETRY_SECONDS)
    logger.warning(f"Topic {topic_id} not scanned: the scanner stayed busy")


async def _scan_then_remove(
    download_id: int, topic_ids: list[int], series_ids: list[int], franchise_ids: list[int]
) -> None:
    for topic_id in topic_ids:
        try:
            await _scan(topic_id)
        except Exception as e:
            logger.warning(f"Scan of topic {topic_id} failed: {e}")
    # After the scan, which puts a season's episodes back in their series: only a title
    # that a correction really emptied goes (a failed scan doesn't bring an empty one back)
    if series_ids or franchise_ids:
        try:
            async with async_session_maker() as session:
                await session.execute(
                    delete(Series).where(Series.id.in_(series_ids), ~Series.episodes.any())
                )
                await session.execute(
                    delete(Franchise).where(
                        Franchise.id.in_(franchise_ids), ~Franchise.concerts.any()
                    )
                )
                await session.commit()
        except Exception as e:
            logger.warning(f"Download {download_id}: empty titles not pruned: {e}")
    # The files are on Telegram whatever the scan did: a later scan finds what it missed
    try:
        async with async_session_maker() as session:
            download = await session.get(Download, download_id)
            # Only after the upload: a move's scan (Task 4) must not remove a running torrent
            if download is not None and download.status == DownloadStatus.scanning:
                download.action, download.status = "remove", DownloadStatus.removing
                await session.commit()
    except Exception as e:
        logger.warning(f"Download {download_id}: removal not ordered: {e}")


def schedule_scan(
    download_id: int,
    topic_ids: list[int],
    series_ids: list[int] | None = None,
    franchise_ids: list[int] | None = None,
) -> None:
    """Scan the topics in the background, then delete those of these series and franchises
    left without titles and, if the download was waiting for this scan, tell the agent to
    remove the torrent."""
    task = asyncio.create_task(
        _scan_then_remove(download_id, topic_ids, series_ids or [], franchise_ids or [])
    )
    _tasks[task] = download_id
    task.add_done_callback(_tasks.pop)
