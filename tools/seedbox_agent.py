"""The seedbox agent: TLEX's downloads, from qBittorrent to the Telegram group.

Runs on the seedbox next to qBittorrent and talks only outwards: every 3 s it reports TLEX's
torrents and uploads to TLEX and gets its commands back. It reads and touches only the
torrents in the TLEX category tagged tlex-<download id>, never the user's other ones.

  python3 seedbox_agent.py login +39...       its own Telegram login (session "agent")
  python3 seedbox_agent.py code 12345 [pwd]   hand the code (and two-step password) to it
  python3 seedbox_agent.py password <pwd>     the two-step password, if the login asks
  python3 seedbox_agent.py run                the agent (start-agent.sh runs it in background)

~/.tlex-upload/agent.json, chmod 600: {"tlex_url": "https://...", "token": "...",
  "qbit_url": "https://...", "qbit_user": "...", "qbit_password": "...",
  "path_map": ["/home4/sante/storage", "/storage"]}  (qBittorrent's root, then the shell's)
The group and the Telegram app come from ~/.tlex-upload/config.json, as for telegram_upload.py.
"""

import asyncio
import base64
import json
import os
import posixpath
import re
import secrets
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import telegram_upload
from telegram_upload import PART_SIZE, _load, _log, _save

# Never the uploader's session: one session used by two processes gets revoked
telegram_upload.SESSION = "agent"

HOME = telegram_upload.HOME
AGENT_CONFIG = HOME / "agent.json"
STATE = HOME / "agent-state.json"  # "<download id>|<path>|<part>" -> message id
CATEGORY = "TLEX"
TAG = re.compile(r"tlex-(\d+)")
# One torrent's hash: never "all" or a "|" list, which reach the user's other torrents
HASH = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
SYNC_SECONDS = 3
RETRY_SECONDS = 10
# A torrent just added shows up in qBittorrent's list a moment later, and a finished file
# may still be renamed from .!qB: missing for this long, it is not coming
GRACE_SECONDS = 60


def local_path(qbit_path: str, path_map: list[str]) -> str:
    """qBittorrent's path as the shell sees it (qBittorrent runs in another container)."""
    qbit_root, shell_root = (p.rstrip("/") for p in path_map)
    if qbit_path == qbit_root or qbit_path.startswith(qbit_root + "/"):
        return shell_root + qbit_path[len(qbit_root) :]
    return qbit_path


def _opener(*handlers) -> urllib.request.OpenerDirector:
    opener = urllib.request.build_opener(*handlers)
    # Python's default user agent is one that proxies and Cloudflare tend to turn away
    opener.addheaders = [("User-Agent", "tlex-seedbox-agent")]
    return opener


def _multipart(fields: dict[str, str], torrent: bytes | None) -> tuple[bytes, str]:
    boundary = secrets.token_hex(16)
    parts = [(f'name="{name}"', value.encode()) for name, value in fields.items()]
    if torrent:
        file = 'name="torrents"; filename="tlex.torrent"\r\nContent-Type: application/x-bittorrent'
        parts.append((file, torrent))
    body = b"".join(
        f"--{boundary}\r\nContent-Disposition: form-data; {head}\r\n\r\n".encode() + value + b"\r\n"
        for head, value in parts
    )
    return body + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


class QBit:
    """qBittorrent's WebUI API v2: TLEX's category, and writes on one torrent at a time."""

    def __init__(self, url: str, user: str, password: str, opener=None):
        self.api = url.rstrip("/") + "/api/v2/"
        self.user, self.password = user, password
        self.opener = opener or _opener(urllib.request.HTTPCookieProcessor())

    def _open(self, path: str, data: bytes | None, headers: dict) -> bytes:
        request = urllib.request.Request(self.api + path, data=data, headers=headers)
        with self.opener.open(request, timeout=30) as response:
            return response.read()

    def _call(self, path: str, data: bytes | None = None, headers: dict | None = None) -> bytes:
        try:
            return self._open(path, data, headers or {})
        except urllib.error.HTTPError as e:
            if e.code != 403:
                raise
        # The platform restarts qBittorrent every few hours: its session is gone
        self.login()
        return self._open(path, data, headers or {})

    def _write(self, action: str, hash_: str, **fields: str) -> None:
        if not HASH.fullmatch(hash_):
            raise ValueError(f"Not one torrent's hash: {hash_!r}")
        self._call(
            f"torrents/{action}", urllib.parse.urlencode({"hashes": hash_, **fields}).encode()
        )

    def _either(self, action: str, old: str, hash_: str) -> None:
        try:
            self._write(action, hash_)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            self._write(old, hash_)  # qBittorrent 4

    def login(self) -> None:
        form = urllib.parse.urlencode({"username": self.user, "password": self.password})
        if self._open("auth/login", form.encode(), {}).strip() != b"Ok.":
            raise RuntimeError("qBittorrent refused the login: check qbit_user and qbit_password")

    def torrents(self) -> list[dict]:
        query = urllib.parse.urlencode({"category": CATEGORY})
        listed = json.loads(self._call(f"torrents/info?{query}"))
        return [t for t in listed if t.get("category") == CATEGORY]

    def files(self, hash_: str) -> list[dict]:
        return json.loads(self._call("torrents/files?" + urllib.parse.urlencode({"hash": hash_})))

    def add(self, download_id: int, magnet: str | None, torrent: bytes | None, savepath: str):
        """ValueError when qBittorrent refuses it (a broken .torrent, one it already has)."""
        fields = {
            "savepath": savepath,
            "category": CATEGORY,
            "tags": f"tlex-{download_id}",
            # Exactly in savepath: no category folder, no folder for incomplete torrents
            "autoTMM": "false",
            "useDownloadPath": "false",
        }
        if magnet:
            fields["urls"] = magnet
        body, content_type = _multipart(fields, torrent)
        try:
            answer = self._call("torrents/add", body, {"Content-Type": content_type})
        except urllib.error.HTTPError as e:
            if e.code not in (400, 409, 415):
                raise
            answer = b"Fails."
        if answer.strip() == b"Fails.":
            raise ValueError("qBittorrent non ha accettato il torrent")

    def top(self, hash_: str) -> None:
        self._write("topPrio", hash_)

    def pause(self, hash_: str) -> None:
        self._either("stop", "pause", hash_)

    def resume(self, hash_: str) -> None:
        self._either("start", "resume", hash_)

    def delete(self, hash_: str) -> None:
        self._write("delete", hash_, deleteFiles="true")


def _torrent(download_id: int, t: dict) -> dict:
    return {
        "download_id": download_id,
        **{k: t[k] for k in ("hash", "state", "progress", "dlspeed", "upspeed", "eta", "size")},
        "num_peers": t["num_seeds"] + t["num_leechs"],
        "num_seeds": t["num_seeds"],
        "files": [
            {"path": f["name"], "size": f["size"], "progress": f["progress"]} for f in t["files"]
        ],
    }


class Agent:
    def __init__(self, config: dict, qbit, client, chat_id: int, part_size: int, opener=None):
        self.config, self.qbit, self.client = config, qbit, client
        self.chat_id, self.part_size = chat_id, part_size
        self.path_map: list[str] = config["path_map"]
        self.opener = opener or _opener()
        self.state: dict = _load(STATE, {})
        self.torrents: dict[int, dict] = {}  # by download id, with their files: the last tick's
        self.plans: dict[int, list[dict]] = {}  # the files left to upload, by download id
        # Commands not applied yet (qBittorrent was down, or hasn't listed the torrent yet)
        self.adds: dict[int, dict] = {}
        self.actions: dict[int, str] = {}  # pause, resume or remove
        self.unseen: dict[int, float] = {}  # added, not listed yet: since when
        # For the next sync
        self.uploads: list[dict] = []
        self.removed: list[int] = []
        self.errors: list[dict] = []
        self.current: dict | None = None
        self.done: set[tuple[int, str]] = set()  # files uploaded (or given up) in this run
        self.missing: dict[tuple[int, str], float] = {}
        self.uploading: int | None = None
        self.upload_task: asyncio.Task | None = None

    def _listing(self) -> dict[int, dict]:
        found = {}
        for t in self.qbit.torrents():
            for tag in t["tags"].split(","):
                if match := TAG.fullmatch(tag.strip()):
                    found[int(match[1])] = {**t, "files": self.qbit.files(t["hash"])}
        return found

    def _sync(self, report: dict) -> dict:
        request = urllib.request.Request(
            self.config["tlex_url"].rstrip("/") + "/api/v1/downloads/agent/sync",
            data=json.dumps(report).encode(),
            headers={"Content-Type": "application/json", "X-Agent-Token": self.config["token"]},
        )
        with self.opener.open(request, timeout=30) as response:
            return json.loads(response.read())

    async def tick(self) -> None:
        """Report TLEX's torrents and the uploads, then apply the commands that come back.
        Without qBittorrent's list there is no sync: a remove would find no torrent."""
        self.torrents = await asyncio.to_thread(self._listing)
        sent = len(self.uploads), len(self.removed), len(self.errors)
        report = {
            "free_bytes": shutil.disk_usage(self.path_map[1]).free,
            # TLEX's torrents only: the other ones are not the agent's business
            "dl_speed": sum(t["dlspeed"] for t in self.torrents.values()),
            "up_speed": sum(t["upspeed"] for t in self.torrents.values()),
            "torrents": [_torrent(i, t) for i, t in self.torrents.items()],
            "uploads": self.uploads[: sent[0]],
            "current_upload": self.current,
            "removed": self.removed[: sent[1]],
            "errors": self.errors[: sent[2]],
        }
        commands = await asyncio.to_thread(self._sync, report)
        # Delivered (the upload may have added more meanwhile)
        del self.uploads[: sent[0]], self.removed[: sent[1]], self.errors[: sent[2]]
        for add in commands.get("add", []):
            self.adds[add["download_id"]] = add
        for action in ("pause", "resume", "remove"):
            for download_id in commands.get(action, []):
                self.actions[download_id] = action
        self.plans = {p["download_id"]: p["files"] for p in commands.get("plans", [])}
        await self._apply()

    async def _apply(self) -> None:
        now = time.monotonic()
        for download_id, since in list(self.unseen.items()):
            if (t := self.torrents.get(download_id)) is not None:
                try:
                    await asyncio.to_thread(self.qbit.top, t["hash"])  # ahead of the queue
                except Exception as e:
                    _log(f"Download {download_id}: not moved to the top: {e!r}")
            elif now - since > GRACE_SECONDS:
                # TLEX sends an add once: without this it would stay queued forever
                error = "qBittorrent non ha aggiunto il torrent"
                self.errors.append({"download_id": download_id, "error": error})
            else:
                continue
            del self.unseen[download_id]

        root = self.path_map[0].rstrip("/")
        for download_id, add in list(self.adds.items()):
            # Listed: an earlier try got there and only its answer was lost
            if download_id not in self.torrents and self.actions.get(download_id) != "remove":
                try:
                    b64 = add["torrent_b64"]
                    torrent = base64.b64decode(b64) if b64 else None
                    savepath = f"{root}/downloads/qbittorrent/tlex/{download_id}"
                    await asyncio.to_thread(
                        self.qbit.add, download_id, add["magnet"], torrent, savepath
                    )
                    self.unseen[download_id] = time.monotonic()
                    _log(f"Download {download_id}: added")
                except ValueError as e:
                    self.errors.append({"download_id": download_id, "error": str(e)})
                except Exception as e:
                    _log(f"Download {download_id}: not added yet: {e!r}")
                    continue
            del self.adds[download_id]

        for download_id, action in list(self.actions.items()):
            t = self.torrents.get(download_id)
            if t is None and (download_id in self.unseen or download_id in self.adds):
                continue  # on its way into qBittorrent
            try:
                if action == "remove":
                    await self._remove(download_id, t)
                elif t is not None:
                    await asyncio.to_thread(getattr(self.qbit, action), t["hash"])
            except Exception as e:
                _log(f"Download {download_id}: {action} failed, trying again: {e!r}")
                continue
            del self.actions[download_id]
            _log(f"Download {download_id}: {action}")

    async def _remove(self, download_id: int, t: dict | None) -> None:
        """Off the seedbox; and off Telegram, the parts of a file left half uploaded."""
        if self.uploading == download_id and self.upload_task is not None:
            self.upload_task.cancel()
            await asyncio.wait([self.upload_task])
        prefix = f"{download_id}|"
        partial = []
        for key, meta in self.state.items():
            if key.startswith(prefix) and key.endswith("|file"):
                ids = [self.state.get(f"{key[:-5]}|{i}") for i in range(meta["parts"])]
                if None in ids:
                    partial += [i for i in ids if i is not None]
        if partial:
            await self.client.delete_messages(self.chat_id, partial)
        if t is not None:
            # Found by its tlex-<id> tag, never by a hash: another download may share it
            await asyncio.to_thread(self.qbit.delete, t["hash"])
        for key in [k for k in self.state if k.startswith(prefix)]:
            del self.state[key]
        _save(STATE, self.state)
        self.plans.pop(download_id, None)
        self.removed.append(download_id)

    def start_upload(self) -> None:
        """A new upload pass once the last one is over: uploads run beside the syncs."""
        task = self.upload_task
        if task is not None:
            if not task.done():
                return
            if not task.cancelled() and task.exception() is not None:
                _log(f"Upload stopped, trying again: {task.exception()!r}")
        self.upload_task = asyncio.create_task(self.upload_ready())

    async def upload_ready(self) -> None:
        """Upload, part by part, the planned files that qBittorrent has finished."""
        try:
            while job := self._next_ready():
                await self._upload(*job)
        finally:
            self.current = self.uploading = None

    def _next_ready(self) -> tuple | None:
        now = time.monotonic()
        for download_id, planned in self.plans.items():
            t = self.torrents.get(download_id)
            if t is None or self.actions.get(download_id) == "remove":
                continue
            finished = {f["name"]: f["size"] for f in t["files"] if f["progress"] >= 1}
            for p in planned:
                path = p["path"]
                if path not in finished or (download_id, path) in self.done:
                    continue
                local = posixpath.join(local_path(t["save_path"], self.path_map), path)
                if os.path.isfile(local):
                    return download_id, path, local, finished[path], p["topic"]
                if now - self.missing.setdefault((download_id, path), now) > GRACE_SECONDS:
                    self.done.add((download_id, path))
                    error = f"File non trovato sulla seedbox: {local}"
                    self.errors.append({"download_id": download_id, "error": error})
        return None

    async def _upload(self, download_id: int, path: str, local: str, size: int, topic) -> None:
        self.uploading = download_id
        key = f"{download_id}|{path}"
        meta = self.state.get(f"{key}|file")
        if meta is None:
            # The whole file goes where its first part went: a correction made meanwhile
            # reaches TLEX through the report's topic, and TLEX moves the file
            meta = {
                "topic_id": await self._topic_id(topic),
                "topic": topic,
                "part_size": self.part_size,
                "parts": -(-size // self.part_size),
            }
            self.state[f"{key}|file"] = meta
            _save(STATE, self.state)
        name, part_size, parts = posixpath.basename(path), meta["part_size"], meta["parts"]
        for i in range(parts):
            if f"{key}|{i}" in self.state:
                continue
            offset = i * part_size
            self.state[f"{key}|{i}"] = await telegram_upload._send(
                self.client,
                self.chat_id,
                meta["topic_id"],
                local,
                name if parts == 1 else f"{name}.{i + 1:03d}",
                offset,
                min(part_size, size - offset),
                on_progress=self._progress(download_id, path, i, parts, offset, size),
            )
            _save(STATE, self.state)
        self.uploads.append(
            {
                "download_id": download_id,
                "path": path,
                "topic_id": meta["topic_id"],
                "message_ids": [self.state[f"{key}|{i}"] for i in range(parts)],
                "topic": meta["topic"],
            }
        )
        self.done.add((download_id, path))
        _log(f"Download {download_id}: {path} uploaded to topic {meta['topic_id']}")

    def _progress(self, download_id: int, path: str, part: int, parts: int, offset: int, size: int):
        started = time.monotonic()

        def on_progress(current: int, total: int) -> None:
            speed = current / max(time.monotonic() - started, 1e-6)
            done = offset + current
            self.current = {
                "download_id": download_id,
                "path": path,
                "part": part + 1,
                "parts": parts,
                "percent": round(done * 100 / size, 1),
                "speed": round(speed),
                "eta": round((size - done) / speed) if speed else None,
            }

        on_progress(0, 0)
        return on_progress

    async def _topic_id(self, topic: str | int) -> int:
        if isinstance(topic, int):
            return topic
        # Listed again each time: TLEX (a move) may have just created it
        known = await telegram_upload._topics(self.client, self.chat_id)
        if topic.casefold() not in known:
            created = await self.client.create_forum_topic(self.chat_id, topic)
            known[topic.casefold()] = created.message_thread_id or created.id
            _log(f"New topic: {topic} ({known[topic.casefold()]})")
        return known[topic.casefold()]


async def run() -> None:
    config = _load(AGENT_CONFIG, None)
    if not config:
        sys.exit(f"Missing {AGENT_CONFIG}")
    AGENT_CONFIG.chmod(0o600)  # the token and qBittorrent's password
    qbit = QBit(config["qbit_url"], config["qbit_user"], config["qbit_password"])
    async with telegram_upload._client() as client:
        me = await client.get_me()
        chat_id = _load(telegram_upload.CONFIG, {})["chat_id"]
        agent = Agent(config, qbit, client, chat_id, PART_SIZE[bool(me.is_premium)])
        _log(f"Agent running as {me.first_name}, syncing with {config['tlex_url']}")
        while True:
            try:
                await agent.tick()
                wait = SYNC_SECONDS
            except Exception as e:
                _log(f"Sync failed: {e!r}")
                wait = RETRY_SECONDS
            agent.start_upload()
            await asyncio.sleep(wait)


if __name__ == "__main__":
    command, *args = sys.argv[1:] or ["help"]
    commands = {
        "login": telegram_upload.login,
        "code": telegram_upload.code,
        "password": telegram_upload.password,
        "run": run,
    }
    if command not in commands:
        sys.exit(__doc__)
    HOME.mkdir(mode=0o700, exist_ok=True)
    asyncio.run(commands[command](*args))
