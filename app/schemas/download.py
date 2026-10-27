"""The Download page's and the seedbox agent's request/response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.download import DownloadKind

# "<name> - Stagione NNN" within Telegram's 128-character topic titles
NAME_MAX = 110


class SeedboxStatus(BaseModel):
    connected: bool
    # The agent syncs, but can't list qBittorrent (it restarts every few hours)
    qbit_connected: bool
    last_seen: float | None
    free_bytes: int | None
    dl_speed: int | None
    up_speed: int | None


class DownloadFile(BaseModel):
    path: str
    size: int
    topic: str | int
    topic_id: int | None
    progress: float
    message_ids: list[int]
    uploaded: bool


class DownloadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    name: str | None
    season: int | None
    torrent_name: str | None
    status: str
    paused: bool
    error: str | None
    files: list[DownloadFile]
    live: dict | None
    upload: dict | None
    created_at: datetime
    finished_at: datetime | None

    @computed_field
    @property
    def topics(self) -> list[str | int]:
        return list(dict.fromkeys(f.topic for f in self.files))


class DownloadsResponse(BaseModel):
    seedbox: SeedboxStatus
    downloads: list[DownloadOut]


class TorrentPreview(BaseModel):
    torrent_name: str | None
    name: str | None
    season: int | None


class DownloadUpdate(BaseModel):
    kind: DownloadKind
    name: str | None = Field(None, max_length=NAME_MAX)
    season: int | None = None


# The agent's paths are qBittorrent file names, relative to the torrent's save path.
class AgentFile(BaseModel):
    path: str
    size: int
    progress: float


class AgentTorrent(BaseModel):
    download_id: int
    hash: str
    state: str
    progress: float
    dlspeed: int
    upspeed: int
    num_peers: int
    num_seeds: int
    eta: int
    size: int
    files: list[AgentFile] = []


class AgentUpload(BaseModel):
    """A file all of whose parts are on Telegram."""

    download_id: int
    path: str
    topic_id: int
    message_ids: list[int]
    # The topic it went to: a correction made during its upload doesn't reach it
    topic: str | int | None = None


class AgentCurrentUpload(BaseModel):
    download_id: int
    path: str
    part: int
    parts: int
    percent: float
    speed: float
    eta: float | None = None


class AgentError(BaseModel):
    download_id: int
    error: str


class AgentSync(BaseModel):
    free_bytes: int
    dl_speed: int
    up_speed: int
    # False: qBittorrent can't be listed now, so `torrents` is empty, not "all gone"
    qbit_connected: bool = True
    torrents: list[AgentTorrent] = []
    uploads: list[AgentUpload] = []
    current_upload: AgentCurrentUpload | None = None
    removed: list[int] = []
    errors: list[AgentError] = []


class AgentAdd(BaseModel):
    download_id: int
    magnet: str | None
    torrent_b64: str | None


class AgentPlanFile(BaseModel):
    path: str
    topic: str | int


class AgentPlan(BaseModel):
    download_id: int
    files: list[AgentPlanFile]


class AgentCommands(BaseModel):
    add: list[AgentAdd] = []
    pause: list[int] = []
    resume: list[int] = []
    remove: list[int] = []
    plans: list[AgentPlan] = []
