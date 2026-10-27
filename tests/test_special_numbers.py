"""A special's number from its file name, where guessit reads none.

Laid-Back Camp's three OVAs ("..._OVA01_Heya_Camp_...") came out as S00E01 all three: a
series' file without an episode was taken for its first special.
"""

import pytest

from app.services.scanner.processor import special_number


@pytest.mark.parametrize(
    "name, number",
    [
        ("Rakuen_Kumachi_Yuru_Camp△_OVA01_Heya_Camp_BD_1080p_Hi10P_FLAC_A045614D.mkv", 1),
        ("Rakuen_Kumachi_Yuru_Camp△_OVA03_Saba_Camp_BD_1080p_Hi10P_FLAC_D18C8A5B.mkv", 3),
        ("[Group] Show - OVA 2 [1080p].mkv", 2),
        ("Show - SP01.mkv", 1),
        ("Show Special 3.mkv", 3),
        ("Show.Speciale.12.ITA.mkv", 12),
        ("Show - ONA 4 (720p).mkv", 4),
        # Not a special's number
        ("Show OVA 1080p.mkv", None),
        ("Show.S01E05.DTS-HD.MA.5.1.mkv", None),
        ("Spaceballs.1987.mkv", None),
    ],
)
def test_a_specials_number_is_read_from_its_name(name, number):
    assert special_number(name) == number
