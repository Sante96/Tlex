"""Upload videos to the TLEX Telegram group, in the layout the scanner reads.

Runs where the files are (a seedbox): nothing goes through another PC, nothing is copied
to disk. Its own Telegram login, kept in ~/.tlex-upload: never a TLEX worker's session
string, which would then be used by two places at once (Telegram revokes such keys).

  python3 telegram_upload.py login +39...         send the login code, then wait for it
  python3 telegram_upload.py code 12345 [pwd]     hand the code to the waiting login
                                                  (pwd: the two-step password, if any)
  python3 telegram_upload.py password <pwd>       the two-step password, if the login asks
  python3 telegram_upload.py topics               the group's topics
  python3 telegram_upload.py upload plan.json     upload the plan, in order; resumable

~/.tlex-upload/config.json: {"api_id": ..., "api_hash": "...", "chat_id": -100...}
A plan is a JSON list of {"path": "/storage/.../file.mkv", "topic": "Concerti · Arknights"}
("topic": a title, created if missing, or a topic id). A file over the account's limit
goes up as name.mkv.001, .002, ... (the scanner joins them).
"""

import asyncio
import io
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

from pyrogram import Client
from pyrogram.errors import FloodWait, PasswordHashInvalid, SessionPasswordNeeded

HOME = Path.home() / ".tlex-upload"
CONFIG = HOME / "config.json"
STATE = HOME / "state.json"  # path|part -> message id: what's done, for resuming
CODE = HOME / "code.json"  # from `code` to the waiting `login`
PASSWORD = HOME / "password.json"  # from `password`, if two-step verification is on
CODE_WAIT = 15 * 60
SESSION = "uploader"
# Under Telegram's limits (2000 MiB, 4000 MiB for Premium)
PART_SIZE = {False: 2_000_000_000, True: 4_000_000_000}
RETRIES = 3


class FileSlice(io.RawIOBase):
    """A window of a file, read in place: a part of a big file without writing it out."""

    def __init__(self, path: str, offset: int, length: int, name: str):
        self._file = open(path, "rb")  # noqa: SIM115 (closed with the slice)
        self._start, self._length, self._pos = offset, length, 0
        self.name = name

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, pos: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self._length}[whence]
        self._pos = max(0, min(self._length, base + pos))
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self._length - self._pos
        size = min(size, self._length - self._pos)
        self._file.seek(self._start + self._pos)
        data = self._file.read(size)
        self._pos += len(data)
        return data

    def close(self) -> None:
        self._file.close()
        super().close()


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)  # never a half-written state


def _client() -> Client:
    config = _load(CONFIG, None)
    if not config:
        sys.exit(f"Missing {CONFIG}")
    return Client(SESSION, config["api_id"], config["api_hash"], workdir=str(HOME))


def _log(text: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), text, flush=True)


async def _wait_for(path: Path, client: Client) -> dict:
    """What `code`/`password` hand over, through a file (the login can't be interactive)."""
    deadline = time.monotonic() + CODE_WAIT
    while not path.exists():
        if time.monotonic() > deadline:
            await client.disconnect()
            sys.exit(f"Nothing in {path.name} after {CODE_WAIT // 60} minutes")
        await asyncio.sleep(2)
    given = _load(path, {})
    path.unlink()
    return given


async def login(phone: str) -> None:
    """Code and two-step password on one connection: Telegram forgets a half-done login
    on reconnecting (PHONE_CODE_EXPIRED, then AUTH_KEY_UNREGISTERED)."""
    CODE.unlink(missing_ok=True)
    PASSWORD.unlink(missing_ok=True)
    client = _client()
    await client.connect()
    sent = await client.send_code(phone)
    _log(f"Code sent: run `code <code>` within {CODE_WAIT // 60} minutes")
    given = await _wait_for(CODE, client)
    try:
        await client.sign_in(phone, sent.phone_code_hash, given["code"])
    except SessionPasswordNeeded:
        secret = given.get("password")
        while True:
            if not secret:
                _log("Two-step verification is on: run `password <password>`")
                secret = (await _wait_for(PASSWORD, client))["password"]
            try:
                await client.check_password(secret)
                break
            except PasswordHashInvalid:
                _log("Wrong password")
                secret = None
    me = await client.get_me()
    await client.disconnect()
    _log(f"Signed in as {me.first_name} (Premium: {me.is_premium})")


async def code(value: str, secret: str | None = None) -> None:
    _save(CODE, {"code": value, "password": secret})
    CODE.chmod(0o600)


async def password(secret: str) -> None:
    _save(PASSWORD, {"password": secret})
    PASSWORD.chmod(0o600)


async def _topics(client: Client, chat_id: int) -> dict[str, int]:
    return {t.name.casefold(): t.message_thread_id async for t in client.get_forum_topics(chat_id)}


async def topics() -> None:
    async with _client() as client:
        chat_id = _load(CONFIG, {})["chat_id"]
        async for t in client.get_forum_topics(chat_id):
            print(t.message_thread_id, t.name)


async def _existing(client: Client, chat_id: int) -> set[tuple[int, str]]:
    """(topic, file name) of every file already in the group: those are skipped."""
    found = set()
    # Pyrogram annotates its async generators as coroutines
    async for message in client.get_chat_history(chat_id):  # pyright: ignore[reportGeneralTypeIssues]
        media = message.document or message.video
        if media and media.file_name:
            found.add((message.message_thread_id or 1, media.file_name))
    return found


async def _send(
    client: Client,
    chat_id: int,
    topic: int,
    path: str,
    name: str,
    offset: int,
    length: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    started, last = time.monotonic(), [0.0]

    async def progress(current: int, total: int) -> None:
        if on_progress is not None:
            on_progress(current, total)
        now = time.monotonic()
        if now - last[0] >= 60 or current == total:
            last[0] = now
            speed = current / max(now - started, 1e-6) / 1e6
            _log(f"  {name}: {current * 100 // max(total, 1)}% ({speed:.1f} MB/s)")

    for attempt in range(1, RETRIES + 1):
        with FileSlice(path, offset, length, name) as part:
            try:
                message = await client.send_document(
                    chat_id,
                    part,  # pyright: ignore[reportArgumentType]  (any binary file object)
                    file_name=name,
                    message_thread_id=topic,
                    progress=progress,
                )
                if message is None:  # only for a stopped upload: never stopped here
                    raise RuntimeError("upload stopped")
                return message.id
            except FloodWait as e:
                # Typed int | str | error: for FLOOD_WAIT_X always the int
                wait = e.value if isinstance(e.value, int) else 1
                _log(f"  flood wait {wait} s")
                await asyncio.sleep(wait + 1)
            except Exception as e:  # network drops: try again, then leave it for a rerun
                _log(f"  {name}: attempt {attempt} failed: {e!r}")
                if attempt == RETRIES:
                    raise
                await asyncio.sleep(30 * attempt)
    raise RuntimeError(f"{name}: gave up")


async def upload(plan_file: str) -> None:
    plan = json.loads(Path(plan_file).read_text(encoding="utf-8"))
    state = _load(STATE, {})
    chat_id = _load(CONFIG, {})["chat_id"]
    async with _client() as client:
        me = await client.get_me()
        part_size = PART_SIZE[bool(me.is_premium)]
        known = await _topics(client, chat_id)
        existing = await _existing(client, chat_id)
        total = sum(os.path.getsize(item["path"]) for item in plan)
        _log(f"{len(plan)} files, {total / 1e9:.0f} GB, parts of {part_size / 1e9:.0f} GB")

        done_bytes, started = 0, time.monotonic()
        for n, item in enumerate(plan, 1):
            path, topic = item["path"], item["topic"]
            if isinstance(topic, str):
                if topic.casefold() not in known:
                    # The topic's id is its creation message's
                    created = await client.create_forum_topic(chat_id, topic)
                    known[topic.casefold()] = created.message_thread_id or created.id
                    _log(f"New topic: {topic} ({known[topic.casefold()]})")
                topic = known[topic.casefold()]
            size = os.path.getsize(path)
            name = os.path.basename(path)
            parts = (size + part_size - 1) // part_size
            _log(f"[{n}/{len(plan)}] {name} ({size / 1e9:.1f} GB, {parts} parts) → topic {topic}")
            for i in range(parts):
                part_name = name if parts == 1 else f"{name}.{i + 1:03d}"
                key = f"{path}|{i}"
                if key in state or (topic, part_name) in existing:
                    continue
                offset = i * part_size
                length = min(part_size, size - offset)
                state[key] = await _send(client, chat_id, topic, path, part_name, offset, length)
                _save(STATE, state)
            done_bytes += size
            rate = done_bytes / max(time.monotonic() - started, 1) / 1e6
            _log(f"  done; {done_bytes / 1e9:.0f}/{total / 1e9:.0f} GB, {rate:.1f} MB/s overall")
    _log("Plan uploaded")


if __name__ == "__main__":
    command, *args = sys.argv[1:] or ["help"]
    commands = {
        "login": login,
        "code": code,
        "password": password,
        "topics": topics,
        "upload": upload,
    }
    if command not in commands:
        sys.exit(__doc__)
    HOME.mkdir(mode=0o700, exist_ok=True)
    asyncio.run(commands[command](*args))
