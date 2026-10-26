"""Matching a film's file name on TMDB when the plain search finds nothing.

File names don't always carry TMDB's title: "Tremors 1" (TMDB: "Tremors"), a year off by
one ("Tremors 4 … (2003)", released 2004), the Italian title and the original run together
("I mercenari The Expendables 4"), or the original only as guessit's alternative title
("Frankenstein Yunior - Young Frankenstein"). The fallbacks below find those; each of their
answers must be from the file's year, give or take one, or it's some other film.
"""

import re

from app.services.tmdb import tmdb_client
from app.services.tmdb.models import TMDBResult

MIN_WORDS = 2  # a part of the title tried on its own: at least this many words


def _near(result: TMDBResult | None, year: int) -> bool:
    if result is None or not result.release_date:
        return False
    return abs(int(result.release_date[:4]) - year) <= 1


async def find_movie(title: str, year: int | None, alternatives: list[str]) -> TMDBResult | None:
    """TMDB's film for a file's title (and year, and guessit's alternative titles)."""
    found = await tmdb_client.search_movie(title, year)
    # Without a year nothing tells a wrong guess from a right one: the plain search only
    if found or not year:
        return found

    queries: list[tuple[str, int | None]] = []
    without_one = re.sub(r"\s+1$", "", title)  # a saga's first film has no number on TMDB
    if without_one != title:
        queries.append((without_one, year))
    queries += [(alternative, year) for alternative in alternatives]
    queries.append((title, None))  # the year off by one (accepted within ±1 below)
    # Two titles run together: the end of it (the original), then its start (the Italian)
    words = title.split()
    queries += [(" ".join(words[i:]), year) for i in range(1, len(words) - MIN_WORDS + 1)]
    queries += [(" ".join(words[:i]), year) for i in range(len(words) - 1, MIN_WORDS - 1, -1)]

    for query, query_year in queries:
        found = await tmdb_client.search_movie(query, query_year)
        if _near(found, year):
            return found
    return None
