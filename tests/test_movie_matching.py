"""Matching a film's file name on TMDB when the plain search finds nothing."""

import pytest

from app.services.scanner.movies import find_movie
from app.services.tmdb import tmdb_client
from app.services.tmdb.models import TMDBResult

# What TMDB answers, as observed: with a year only that release year matches; without
# one, the first result whatever its year
FILMS = {
    "tremors": (9362, "Tremors", "1990-01-19"),
    "tremors 4 agli inizi della leggenda": (10891, "Tremors 4 - Agli inizi della leggenda", "2004-01-02"),
    "young frankenstein": (3034, "Frankenstein Junior", "1974-12-15"),
    "the expendables 4": (299054, "I mercen4ri - Expendables", "2023-09-15"),
    "i mercenari": (27578, "I mercenari - The Expendables", "2010-08-03"),
    "versione integrale": (1, "Un film qualsiasi", "1980-01-01"),
}


@pytest.fixture(autouse=True)
def tmdb(mocker):
    queries = []

    async def search_movie(title, year=None, language=None):
        queries.append((title, year))
        found = FILMS.get(title.casefold())
        if not found or (year and found[2][:4] != str(year)):
            return None
        tmdb_id, name, date = found
        return TMDBResult(tmdb_id, name, None, None, None, date, "movie")

    mocker.patch.object(tmdb_client, "search_movie", side_effect=search_movie)
    return queries


async def _id(title, year=None, alternatives=()):
    result = await find_movie(title, year, list(alternatives))
    return result.tmdb_id if result else None


async def test_the_plain_search_comes_first(tmdb):
    assert await _id("Tremors", 1990) == 9362
    assert tmdb == [("Tremors", 1990)]


async def test_a_trailing_1_is_dropped():
    assert await _id("Tremors 1", 1990) == 9362


async def test_a_year_off_by_one_is_accepted():
    assert await _id("Tremors 4 Agli inizi della leggenda", 2003) == 10891


async def test_the_alternative_title_is_tried():
    assert await _id("Frankenstein Yunior", 1974, ["Young Frankenstein", "Versione integrale"]) == 3034


async def test_an_italian_and_an_original_title_run_together():
    assert await _id("I mercenari The Expendables 4", 2023) == 299054


async def test_a_fallback_of_another_year_is_refused():
    # "Versione integrale" exists on TMDB, but from 1980: not this 1974 film
    assert await _id("Frankenstein Yunior", 1974, ["Versione integrale"]) is None


async def test_without_a_year_no_guessing_on_parts_of_the_title(tmdb):
    assert await _id("I mercenari The Expendables 4") is None
    # Only the whole title, as given: nothing could tell a wrong part from a right one
    assert tmdb == [("I mercenari The Expendables 4", None)]
