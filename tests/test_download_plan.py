from unittest.mock import patch

import pytest

from app.models.download import DownloadKind
from app.services.downloads.plan import (
    destination_topic,
    file_topic,
    guess,
    info_hash,
    torrent_name,
    uploadable,
)


@pytest.fixture(autouse=True)
def films_topic():
    with patch("app.services.downloads.plan.get_settings") as s:
        s.return_value.scanner_movies_topic_id = 2
        yield


def test_destination_topics():
    assert destination_topic(DownloadKind.film, None, None) == 2
    assert (
        destination_topic(DownloadKind.series, "Stargate SG-1", 1) == "Stargate SG-1 - Stagione 1"
    )
    assert destination_topic(DownloadKind.anime, "Frieren", 2) == "Frieren - Stagione 2"
    assert destination_topic(DownloadKind.concert, "Love Live!", None) == "Concerti · Love Live!"
    with pytest.raises(ValueError):
        destination_topic(DownloadKind.series, None, 1)


def test_a_pack_sends_each_file_to_its_season():
    def t(p):
        return file_topic(DownloadKind.series, "The Expanse", 1, p)

    assert t("The.Expanse.S02E03.mkv") == "The Expanse - Stagione 2"
    assert t("Episode 05.mkv") == "The Expanse - Stagione 1"
    assert t("The_Expanse_OVA01.mkv") == "The Expanse - Stagione 0"


def test_uploadable_files():
    assert uploadable("Show/S01E01.mkv") and uploadable("Show/S01E01.MP4")
    assert not uploadable("Show/Sample/sample.mkv")
    assert not uploadable("Show/Extras/NCOP1.mkv")
    assert not uploadable("Show/cover.jpg") and not uploadable("Show/disc.iso")


def test_torrent_name():
    assert (
        torrent_name("magnet:?xt=urn:btih:ABC&dn=Stargate.SG-1.S01.1080p", None)
        == "Stargate.SG-1.S01.1080p"
    )
    assert torrent_name("magnet:?xt=urn:btih:ABC", None) is None
    assert torrent_name(None, b"d4:infod4:name9:Some.Showee") == "Some.Show"
    assert torrent_name(None, b"not bencode") is None
    assert torrent_name(None, b"d4:infod4:name99:shortee") is None
    assert info_hash("magnet:?xt=urn:btih:ABCdef&dn=x") == "abcdef"
    assert info_hash("magnet:?dn=x") is None


def test_guess_prefill():
    assert guess("Stargate.SG-1.S01.1080p.BluRay.x264") == {"name": "Stargate SG-1", "season": 1}
