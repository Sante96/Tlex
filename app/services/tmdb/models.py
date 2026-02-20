"""TMDB data models."""

from dataclasses import dataclass


@dataclass
class TMDBResult:
    """TMDB search result."""

    tmdb_id: int
    title: str
    overview: str | None
    poster_path: str | None
    backdrop_path: str | None
    release_date: str | None
    media_type: str  # "movie" or "tv"


@dataclass
class CastMember:
    """Cast/crew member from TMDB."""

    id: int
    name: str
    character: str | None  # For cast
    job: str | None  # For crew
    profile_path: str | None
    order: int = 0


@dataclass
class MovieDetails:
    """Detailed movie information from TMDB."""

    tmdb_id: int
    title: str
    overview: str | None
    poster_path: str | None
    backdrop_path: str | None
    release_date: str | None
    genres: list[str]
    vote_average: float | None
    content_rating: str | None  # e.g. "PG-13", "R", "VM18"


@dataclass
class EpisodeInfo:
    """Episode information from TMDB."""

    episode_number: int
    name: str
    overview: str | None
    still_path: str | None  # Episode thumbnail
    air_date: str | None
    runtime: int | None


@dataclass
class TVDetails:
    """Detailed TV show information from TMDB."""

    tmdb_id: int
    title: str
    overview: str | None
    poster_path: str | None
    backdrop_path: str | None
    first_air_date: str | None
    genres: list[str]
    vote_average: float | None  # Rating 0-10
    content_rating: str | None  # e.g. "TV-MA", "VM18"
