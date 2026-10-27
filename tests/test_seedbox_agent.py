"""The seedbox agent: only TLEX's torrents, qBittorrent's restarts, resumable uploads."""

import io
import json
import sys
import urllib.error
from email import policy
from email.message import Message
from email.parser import BytesParser
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas.download import AgentCurrentUpload, AgentSync, AgentTorrent, AgentUpload

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import seedbox_agent  # noqa: E402  # pyright: ignore[reportMissingImports]

ROOT = "/home4/sante/storage"
HASH = "a" * 40
CHAT = -100


class Opener:
    """Answers each request in turn: bytes, or an HTTP status to fail with."""

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []

    def open(self, request, timeout=None):
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, int):
            raise urllib.error.HTTPError(request.full_url, answer, "", Message(), None)
        return io.BytesIO(answer)


class FakeQBit:
    """qBittorrent's TLEX category; the writes (add, top, pause, resume, delete) are recorded."""

    def __init__(self, *torrents, files=()):
        self.listed, self.file_list, self.calls = list(torrents), list(files), []

    def torrents(self):
        return self.listed

    def files(self, hash_):
        return self.file_list

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, *args))


class Telegram:
    """The agent's client: the group's topics, and the messages it deletes."""

    def __init__(self, topics=None):
        self.topics, self.deleted = topics or {}, []

    async def get_forum_topics(self, chat_id):
        for name, thread in self.topics.items():
            yield SimpleNamespace(name=name, message_thread_id=thread)

    async def delete_messages(self, chat_id, ids):
        self.deleted += ids


def torrent(tags: str, hash_: str = HASH, download_id: int = 3) -> dict:
    return {
        "hash": hash_,
        "category": "TLEX",
        "tags": tags,
        "state": "downloading",
        "progress": 0.5,
        "dlspeed": 100,
        "upspeed": 5,
        "num_seeds": 2,
        "num_leechs": 3,
        "eta": 60,
        "size": 1000,
        "save_path": f"{ROOT}/downloads/qbittorrent/tlex/{download_id}",
    }


@pytest.fixture
def make_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(seedbox_agent, "STATE", tmp_path / "agent-state.json")

    def make(qbit, *commands, client=None, part_size=10):
        config = {
            "tlex_url": "https://tlex.test/",
            "token": "secret-token",
            "path_map": [ROOT, str(tmp_path)],
        }
        opener = Opener(*(json.dumps(c).encode() for c in commands))
        return seedbox_agent.Agent(
            config, qbit, client or Telegram(), CHAT, part_size, opener=opener
        )

    return make


def reports(agent) -> list[dict]:
    return [json.loads(r.data) for r in agent.opener.requests]


def qbit(*answers):
    opener = Opener(*answers)
    return seedbox_agent.QBit("https://qb.test", "sante", "pw", opener=opener), opener


def test_qbit_paths_are_read_from_the_shell():
    assert (
        seedbox_agent.local_path(
            "/home4/sante/storage/downloads/qbittorrent/tlex/7/x.mkv",
            ["/home4/sante/storage", "/storage"],
        )
        == "/storage/downloads/qbittorrent/tlex/7/x.mkv"
    )


def test_qbit_logs_in_again_after_a_restart():
    listed = [torrent("tlex-1")]
    client, opener = qbit(403, b"Ok.", json.dumps(listed).encode())
    assert client.torrents() == listed
    urls = [r.full_url for r in opener.requests]
    assert urls.count("https://qb.test/api/v2/auth/login") == 1
    assert urls[0] == urls[2] == "https://qb.test/api/v2/torrents/info?category=TLEX"


def test_qbit_lists_only_the_tlex_category():
    listed = [torrent("tlex-1"), {**torrent("tlex-2"), "category": "Serie TV"}]
    client, _ = qbit(json.dumps(listed).encode())
    assert client.torrents() == listed[:1]


def test_pause_falls_back_to_the_old_api():
    client, opener = qbit(404, b"")
    client.pause(HASH)
    assert [r.full_url.rsplit("/", 1)[1] for r in opener.requests] == ["stop", "pause"]
    assert opener.requests[1].data == f"hashes={HASH}".encode()


def test_qbit_writes_take_one_hash_never_all():
    client, opener = qbit()
    for write in (client.delete, client.pause, client.resume, client.top):
        with pytest.raises(ValueError):
            write("all")
    assert opener.requests == []


def test_qbit_adds_in_the_tlex_category_with_the_tag():
    client, opener = qbit(b"Ok.")
    client.add(7, None, b"d4:infoe", "/x/tlex/7")
    request = opener.requests[0]
    head = f"Content-Type: {request.get_header('Content-type')}\r\n\r\n".encode()
    form = BytesParser(policy=policy.default).parsebytes(head + request.data)
    fields = {
        part.get_param("name", header="content-disposition"): part.get_payload(decode=True)
        for part in form.iter_parts()
    }
    assert fields == {
        "savepath": b"/x/tlex/7",
        "category": b"TLEX",
        "tags": b"tlex-7",
        "autoTMM": b"false",
        "useDownloadPath": b"false",
        "torrents": b"d4:infoe",
    }


async def test_only_tlex_torrents_are_reported(make_agent):
    fake = FakeQBit(torrent("tlex-3"), torrent("", "b" * 40), torrent("tlex-x", "c" * 40))
    agent = make_agent(fake, {})
    await agent.tick()
    [report] = reports(agent)
    assert [t["download_id"] for t in report["torrents"]] == [3]
    # The backend's contract, field for field
    AgentSync.model_validate(report)
    assert set(report) == set(AgentSync.model_fields)
    assert set(report["torrents"][0]) == set(AgentTorrent.model_fields)
    request = agent.opener.requests[0]
    assert request.full_url == "https://tlex.test/api/v1/downloads/agent/sync"
    assert request.get_header("X-agent-token") == "secret-token"


async def test_an_uploaded_part_is_not_sent_again(make_agent, tmp_path, monkeypatch):
    folder = tmp_path / "downloads/qbittorrent/tlex/5/S"
    folder.mkdir(parents=True)
    (folder / "x.mkv").write_bytes(b"x" * 15)
    seedbox_agent.STATE.write_text(json.dumps({"5|S/x.mkv|0": 101}))
    sent, progress = [], {}

    async def send(client, chat_id, topic, path, name, offset, length, on_progress):
        sent.append((topic, name, offset, length))
        on_progress(length, length)
        progress.update(agent.current)
        return 202

    monkeypatch.setattr(seedbox_agent.telegram_upload, "_send", send)
    fake = FakeQBit(
        torrent("tlex-5", download_id=5), files=[{"name": "S/x.mkv", "size": 15, "progress": 1}]
    )
    plan = {"download_id": 5, "files": [{"path": "S/x.mkv", "topic": "Show - Stagione 1"}]}
    client = Telegram({"Show - Stagione 1": 77})
    agent = make_agent(fake, {"plans": [plan]}, {}, client=client)
    await agent.tick()
    await agent.upload_ready()
    assert sent == [(77, "x.mkv.002", 10, 5)]
    assert set(progress) == set(AgentCurrentUpload.model_fields)
    AgentCurrentUpload.model_validate(progress)
    await agent.tick()
    AgentSync.model_validate(reports(agent)[1])
    assert set(reports(agent)[1]["uploads"][0]) == set(AgentUpload.model_fields)
    assert reports(agent)[1]["uploads"] == [
        {
            "download_id": 5,
            "path": "S/x.mkv",
            "topic_id": 77,
            "message_ids": [101, 202],
            "topic": "Show - Stagione 1",
        }
    ]


async def test_an_add_goes_to_its_folder_tagged_then_to_the_top(make_agent):
    fake = FakeQBit()
    add = {"download_id": 7, "magnet": "magnet:?xt=urn:btih:abc", "torrent_b64": None}
    agent = make_agent(fake, {"add": [add], "pause": [7]}, {})
    await agent.tick()
    folder = f"{ROOT}/downloads/qbittorrent/tlex/7"
    assert fake.calls == [("add", 7, "magnet:?xt=urn:btih:abc", None, folder)]
    # qBittorrent lists it a moment later: then it goes on top, and the pause reaches it
    fake.listed = [torrent("tlex-7", download_id=7)]
    await agent.tick()
    assert fake.calls[1:] == [("top", HASH), ("pause", HASH)]


async def test_an_add_qbittorrent_never_lists_is_an_error(make_agent, monkeypatch):
    monkeypatch.setattr(seedbox_agent, "GRACE_SECONDS", -1)
    add = {"download_id": 7, "magnet": "magnet:?xt=urn:btih:abc", "torrent_b64": None}
    agent = make_agent(FakeQBit(), {"add": [add]}, {}, {})
    for _ in range(3):
        await agent.tick()
    assert [r["errors"] for r in reports(agent)] == [
        [],
        [],
        [{"download_id": 7, "error": "qBittorrent non ha aggiunto il torrent"}],
    ]


async def test_a_remove_without_a_torrent_is_reported(make_agent):
    fake = FakeQBit()
    agent = make_agent(fake, {"remove": [9]}, {})
    await agent.tick()
    await agent.tick()
    assert reports(agent)[1]["removed"] == [9]
    assert fake.calls == []


async def test_a_remove_deletes_only_the_torrent_tagged_with_its_id(make_agent):
    # Download 4 shares download 3's hash (a second .torrent of it): qBittorrent has one
    # torrent, tagged tlex-3, and a remove of 4 must leave it alone
    fake = FakeQBit(torrent("tlex-3"), torrent("", "b" * 40), torrent("other, tlex-x", "c" * 40))
    agent = make_agent(fake, {"remove": [4]}, {"remove": [3]}, {})
    await agent.tick()
    assert fake.calls == []
    await agent.tick()
    assert fake.calls == [("delete", HASH)]
    await agent.tick()
    assert [r["removed"] for r in reports(agent)] == [[], [4], [3]]


async def test_partial_parts_are_deleted_on_remove(make_agent):
    def meta(parts):
        return {"topic_id": 77, "topic": "Show - Stagione 1", "part_size": 10, "parts": parts}

    state = {
        "3|done.mkv|file": meta(2),
        "3|done.mkv|0": 11,
        "3|done.mkv|1": 12,
        "3|half.mkv|file": meta(2),
        "3|half.mkv|0": 21,
        "30|other.mkv|file": meta(2),
        "30|other.mkv|0": 31,
    }
    seedbox_agent.STATE.write_text(json.dumps(state))
    client, fake = Telegram(), FakeQBit(torrent("tlex-3"))
    agent = make_agent(fake, {"remove": [3]}, client=client)
    await agent.tick()
    assert client.deleted == [21]
    assert fake.calls == [("delete", HASH)]
    remaining = json.loads(seedbox_agent.STATE.read_text())
    assert remaining == {k: v for k, v in state.items() if k.startswith("30|")}
