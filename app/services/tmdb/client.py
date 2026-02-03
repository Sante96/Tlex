"""TMDB API client implementation."""

import re

import httpx
from loguru import logger

from app.config import get_settings
from app.services.tmdb.models import CastMember, EpisodeInfo, TMDBResult, TVDetails

settings = get_settings()

TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Patterns to clean from TV show titles (e.g., "Season 1", "Stagione 1")
SEASON_PATTERNS = [
    re.compile(r"\s*[-–—]\s*[Ss]tagione\s*\d+", re.IGNORECASE),
    re.compile(r"\s*[-–—]\s*[Ss]eason\s*\d+", re.IGNORECASE),
    re.compile(r"\s*[Ss]tagione\s*\d+$", re.IGNORECASE),
    re.compile(r"\s*[Ss]eason\s*\d+$", re.IGNORECASE),
    re.compile(r"\s*[Ss]\d+$"),
]



def clean_tv_title(title: str) -> str:
    """
    Remove season indicators from TV show title for TMDB search.

    Args:
        title: The original TV show title.

    Returns:
        The cleaned title used for searching.
    """
    cleaned = title.strip()
    for pattern in SEASON_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()


class TMDBClient:
    """
    Client for interacting with The Movie Database (TMDB) API.

    Handles searching for movies and TV shows, retrieving details,
    credits, and episode information.
    """

    def __init__(self) -> None:
        self._api_key = settings.tmdb_api_key
        self._language = settings.tmdb_language

    async def search_movie(self, title: str, year: int | None = None) -> TMDBResult | None:
        """
        Search for a movie by title.

        Args:
            title: Movie title to search.
            year: Optional release year to narrow results.

        Returns:
            TMDBResult object if found, otherwise None.
        """
        params = {
            "api_key": self._api_key,
            "query": title,
            "language": self._language,
        }
        if year:
            params["year"] = str(year)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/search/movie",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("results"):
                    logger.warning(f"No TMDB results for movie: {title}")
                    return None

                result = data["results"][0]
                return TMDBResult(
                    tmdb_id=result["id"],
                    title=result.get("title", title),
                    overview=result.get("overview"),
                    poster_path=result.get("poster_path"),
                    backdrop_path=result.get("backdrop_path"),
                    release_date=result.get("release_date"),
                    media_type="movie",
                )
            except httpx.HTTPError as e:
                logger.error(f"TMDB API error: {e}")
                return None

    async def search_tv(
        self, title: str, season: int | None = None, episode: int | None = None
    ) -> TMDBResult | None:
        """
        Search for a TV show by title.

        Args:
            title: TV show title.
            season: Optional season number to fetch specific details.
            episode: Optional episode number (currently unused but reserved).

        Returns:
            TMDBResult object if found, otherwise None.
        """
        clean_title = clean_tv_title(title)
        if clean_title != title:
            logger.debug(f"Cleaned TV title: '{title}' -> '{clean_title}'")

        params = {
            "api_key": self._api_key,
            "query": clean_title,
            "language": self._language,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/search/tv",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("results"):
                    logger.warning(f"No TMDB results for TV: {title}")
                    return None

                result = data["results"][0]
                tv_id = result["id"]
                poster_path = result.get("poster_path")
                overview = result.get("overview")

                if season is not None:
                    season_data = await self._get_season_details(client, tv_id, season)
                    if season_data:
                        if season_data.get("poster_path"):
                            poster_path = season_data["poster_path"]
                            logger.debug(f"Using season {season} poster for {result.get('name')}")

                        if season_data.get("overview"):
                            overview = season_data["overview"]

                return TMDBResult(
                    tmdb_id=tv_id,
                    title=result.get("name", title),
                    overview=overview,
                    poster_path=poster_path,
                    backdrop_path=result.get("backdrop_path"),
                    release_date=result.get("first_air_date"),
                    media_type="tv",
                )
            except httpx.HTTPError as e:
                logger.error(f"TMDB API error: {e}")
                return None

    async def _get_season_details(
        self, client: httpx.AsyncClient, tv_id: int, season_number: int
    ) -> dict | None:
        """Get season-specific details including poster (with existing client)."""
        params = {
            "api_key": self._api_key,
            "language": self._language,
        }
        try:
            response = await client.get(
                f"{TMDB_BASE_URL}/tv/{tv_id}/season/{season_number}",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"Could not get season {season_number} details: {e}")
            return None

    async def get_season_details(self, tv_id: int, season_number: int) -> dict | None:
        """Get season-specific details including poster."""
        params = {
            "api_key": self._api_key,
            "language": self._language,
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/tv/{tv_id}/season/{season_number}",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.warning(f"Could not get season {season_number} details: {e}")
                return None

    async def get_movie_details(self, tmdb_id: int) -> TMDBResult | None:
        """Get detailed movie info by TMDB ID."""
        params = {
            "api_key": self._api_key,
            "language": self._language,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                result = response.json()

                return TMDBResult(
                    tmdb_id=result["id"],
                    title=result.get("title", ""),
                    overview=result.get("overview"),
                    poster_path=result.get("poster_path"),
                    backdrop_path=result.get("backdrop_path"),
                    release_date=result.get("release_date"),
                    media_type="movie",
                )
            except httpx.HTTPError as e:
                logger.error(f"TMDB API error: {e}")
                return None

    async def get_movie_credits(self, tmdb_id: int) -> list[CastMember]:
        """Get cast and crew for a movie."""
        params = {
            "api_key": self._api_key,
            "language": self._language,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/movie/{tmdb_id}/credits",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                members: list[CastMember] = []

                # Add cast (actors)
                for person in data.get("cast", [])[:15]:
                    members.append(CastMember(
                        id=person["id"],
                        name=person.get("name", ""),
                        character=person.get("character"),
                        job=None,
                        profile_path=person.get("profile_path"),
                        order=person.get("order", 99),
                    ))

                # Add key crew (directors, writers)
                for person in data.get("crew", []):
                    if person.get("job") in ("Director", "Writer", "Screenplay"):
                        members.append(CastMember(
                            id=person["id"],
                            name=person.get("name", ""),
                            character=None,
                            job=person.get("job"),
                            profile_path=person.get("profile_path"),
                            order=100 + len(members),
                        ))
                        if len([m for m in members if m.job]) >= 5:
                            break

                return members

            except httpx.HTTPError as e:
                logger.error(f"TMDB movie credits error: {e}")
                return []

    async def get_tv_credits(self, tmdb_id: int) -> list[CastMember]:
        """Get cast and crew for a TV show."""
        params = {
            "api_key": self._api_key,
            "language": self._language,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/tv/{tmdb_id}/aggregate_credits",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                members: list[CastMember] = []

                # Add cast (actors)
                for person in data.get("cast", [])[:15]:  # Limit to 15
                    roles = person.get("roles", [])
                    character = roles[0].get("character") if roles else None
                    members.append(CastMember(
                        id=person["id"],
                        name=person.get("name", ""),
                        character=character,
                        job=None,
                        profile_path=person.get("profile_path"),
                        order=person.get("order", 99),
                    ))

                # Add key crew (directors, writers, producers) - limit to 5
                for person in data.get("crew", [])[:5]:
                    jobs = person.get("jobs", [])
                    job = jobs[0].get("job") if jobs else None
                    if job in ("Director", "Writer", "Executive Producer", "Creator"):
                        members.append(CastMember(
                            id=person["id"],
                            name=person.get("name", ""),
                            character=None,
                            job=job,
                            profile_path=person.get("profile_path"),
                            order=100 + len(members),
                        ))

                return members

            except httpx.HTTPError as e:
                logger.error(f"TMDB credits error: {e}")
                return []

    async def get_season_episodes(
        self, tmdb_id: int, season_number: int
    ) -> list[EpisodeInfo]:
        """Get all episodes for a season with thumbnails."""
        params = {
            "api_key": self._api_key,
            "language": self._language,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_number}",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                episodes: list[EpisodeInfo] = []
                for ep in data.get("episodes", []):
                    episodes.append(EpisodeInfo(
                        episode_number=ep.get("episode_number", 0),
                        name=ep.get("name", f"Episode {ep.get('episode_number', '?')}"),
                        overview=ep.get("overview"),
                        still_path=ep.get("still_path"),
                        air_date=ep.get("air_date"),
                        runtime=ep.get("runtime"),
                    ))

                return episodes

            except httpx.HTTPError as e:
                logger.error(f"TMDB episodes error: {e}")
                return []

    async def get_episode_details(
        self, tmdb_id: int, season_number: int, episode_number: int
    ) -> EpisodeInfo | None:
        """Get specific episode details from TMDB."""
        params = {
            "api_key": self._api_key,
            "language": self._language,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                ep = response.json()

                return EpisodeInfo(
                    episode_number=ep.get("episode_number", episode_number),
                    name=ep.get("name", f"Episode {episode_number}"),
                    overview=ep.get("overview"),
                    still_path=ep.get("still_path"),
                    air_date=ep.get("air_date"),
                    runtime=ep.get("runtime"),
                )

            except httpx.HTTPError as e:
                logger.warning(f"Could not get episode S{season_number}E{episode_number}: {e}")
                return None


    async def get_tv_details(self, tmdb_id: int) -> TVDetails | None:
        """
        Get detailed TV show info including genres, rating, and content rating.

        Args:
            tmdb_id: The TMDB ID of the TV show.

        Returns:
            TVDetails object containing extracted information, or None if failed.
        """
        params = {
            "api_key": self._api_key,
            "language": self._language,
            "append_to_response": "content_ratings",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/tv/{tmdb_id}",
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                genres = [g["name"] for g in data.get("genres", [])]

                content_rating = None
                content_ratings = data.get("content_ratings", {}).get("results", [])

                # Priority: IT, then US, then first available
                for cr in content_ratings:
                    if cr.get("iso_3166_1") == "IT":
                        content_rating = cr.get("rating")
                        break
                if not content_rating:
                    for cr in content_ratings:
                        if cr.get("iso_3166_1") == "US":
                            content_rating = cr.get("rating")
                            break
                if not content_rating and content_ratings:
                    content_rating = content_ratings[0].get("rating")

                return TVDetails(
                    tmdb_id=data["id"],
                    title=data.get("name", ""),
                    overview=data.get("overview"),
                    poster_path=data.get("poster_path"),
                    backdrop_path=data.get("backdrop_path"),
                    first_air_date=data.get("first_air_date"),
                    genres=genres,
                    vote_average=data.get("vote_average"),
                    content_rating=content_rating,
                )

            except httpx.HTTPError as e:
                logger.error(f"TMDB TV details error: {e}")
                return None


tmdb_client = TMDBClient()
