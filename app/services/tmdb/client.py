"""TMDB API client implementation."""

import re

import httpx
from loguru import logger

from app.config import get_settings
from app.services.tmdb.models import CastMember, EpisodeInfo, MovieDetails, TMDBResult, TVDetails

settings = get_settings()

TMDB_BASE_URL = "https://api.themoviedb.org/3"

SEASON_PATTERNS = [
    re.compile(r"\s*[-–—]\s*[Ss]tagione\s*\d+", re.IGNORECASE),
    re.compile(r"\s*[-–—]\s*[Ss]eason\s*\d+", re.IGNORECASE),
    re.compile(r"\s*[Ss]tagione\s*\d+$", re.IGNORECASE),
    re.compile(r"\s*[Ss]eason\s*\d+$", re.IGNORECASE),
    re.compile(r"\s*[Ss]\d+$"),
]


def clean_tv_title(title: str) -> str:
    """Remove season indicators from TV show title for TMDB search."""
    cleaned = title.strip()
    for pattern in SEASON_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()


def _image_list(data: list[dict]) -> list[dict]:
    """Extract file_path/width/height from a TMDB image list."""
    return [
        {"file_path": img["file_path"], "width": img.get("width"), "height": img.get("height")}
        for img in data
    ]


class TMDBClient:
    """Client for The Movie Database (TMDB) API."""

    def __init__(self) -> None:
        self._api_key = settings.tmdb_api_key
        self._language = settings.tmdb_language

    async def _get(
        self, path: str, *, use_language: bool = True, **extra
    ) -> dict | None:
        """Shared HTTP GET with error handling."""
        params: dict = {"api_key": self._api_key}
        if use_language:
            params["language"] = self._language
        params.update(extra)
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{TMDB_BASE_URL}{path}", params=params, timeout=10.0
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as e:
                logger.error(f"TMDB API error ({path}): {e}")
                return None

    # --- Movie ---

    async def search_movie(
        self, title: str, year: int | None = None
    ) -> TMDBResult | None:
        """Search for a movie by title."""
        extra: dict = {"query": title}
        if year:
            extra["year"] = str(year)
        data = await self._get("/search/movie", **extra)
        if not data or not data.get("results"):
            logger.warning(f"No TMDB results for movie: {title}")
            return None
        r = data["results"][0]
        return TMDBResult(
            tmdb_id=r["id"], title=r.get("title", title),
            overview=r.get("overview"), poster_path=r.get("poster_path"),
            backdrop_path=r.get("backdrop_path"), release_date=r.get("release_date"),
            media_type="movie",
        )

    async def get_movie_details(self, tmdb_id: int) -> TMDBResult | None:
        """Get detailed movie info by TMDB ID."""
        r = await self._get(f"/movie/{tmdb_id}")
        if not r:
            return None
        return TMDBResult(
            tmdb_id=r["id"], title=r.get("title", ""),
            overview=r.get("overview"), poster_path=r.get("poster_path"),
            backdrop_path=r.get("backdrop_path"), release_date=r.get("release_date"),
            media_type="movie",
        )

    async def get_movie_full_details(self, tmdb_id: int) -> MovieDetails | None:
        """Get full movie details including genres, vote_average, content_rating."""
        r = await self._get(f"/movie/{tmdb_id}", append_to_response="release_dates")
        if not r:
            return None

        genres = [g["name"] for g in r.get("genres", [])]

        # Content rating: prefer IT → US → first available
        content_rating = None
        for entry in r.get("release_dates", {}).get("results", []):
            if entry.get("iso_3166_1") in ("IT", "US"):
                for rd in entry.get("release_dates", []):
                    cert = rd.get("certification", "").strip()
                    if cert:
                        content_rating = cert
                        break
                if content_rating:
                    break
        if not content_rating:
            for entry in r.get("release_dates", {}).get("results", []):
                for rd in entry.get("release_dates", []):
                    cert = rd.get("certification", "").strip()
                    if cert:
                        content_rating = cert
                        break
                if content_rating:
                    break

        return MovieDetails(
            tmdb_id=r["id"], title=r.get("title", ""),
            overview=r.get("overview"), poster_path=r.get("poster_path"),
            backdrop_path=r.get("backdrop_path"), release_date=r.get("release_date"),
            genres=genres, vote_average=r.get("vote_average"),
            content_rating=content_rating,
        )

    async def get_movie_credits(self, tmdb_id: int) -> list[CastMember]:
        """Get cast and crew for a movie."""
        data = await self._get(f"/movie/{tmdb_id}/credits")
        if not data:
            return []

        members: list[CastMember] = []
        for p in data.get("cast", [])[:15]:
            members.append(CastMember(
                id=p["id"], name=p.get("name", ""), character=p.get("character"),
                job=None, profile_path=p.get("profile_path"), order=p.get("order", 99),
            ))
        for p in data.get("crew", []):
            if p.get("job") in ("Director", "Writer", "Screenplay"):
                members.append(CastMember(
                    id=p["id"], name=p.get("name", ""), character=None,
                    job=p.get("job"), profile_path=p.get("profile_path"),
                    order=100 + len(members),
                ))
                if len([m for m in members if m.job]) >= 5:
                    break
        return members

    # --- TV ---

    async def search_tv(
        self, title: str, season: int | None = None, episode: int | None = None
    ) -> TMDBResult | None:
        """Search for a TV show by title."""
        clean_title = clean_tv_title(title)
        if clean_title != title:
            logger.debug(f"Cleaned TV title: '{title}' -> '{clean_title}'")

        data = await self._get("/search/tv", query=clean_title)
        if not data or not data.get("results"):
            logger.warning(f"No TMDB results for TV: {title}")
            return None

        r = data["results"][0]
        poster_path = r.get("poster_path")
        overview = r.get("overview")

        if season is not None:
            sd = await self.get_season_details(r["id"], season)
            if sd:
                if sd.get("poster_path"):
                    poster_path = sd["poster_path"]
                    logger.debug(f"Using season {season} poster for {r.get('name')}")
                if sd.get("overview"):
                    overview = sd["overview"]

        return TMDBResult(
            tmdb_id=r["id"], title=r.get("name", title),
            overview=overview, poster_path=poster_path,
            backdrop_path=r.get("backdrop_path"), release_date=r.get("first_air_date"),
            media_type="tv",
        )

    async def get_tv_details(self, tmdb_id: int) -> TVDetails | None:
        """Get detailed TV show info including genres, rating, content rating."""
        data = await self._get(
            f"/tv/{tmdb_id}", append_to_response="content_ratings"
        )
        if not data:
            return None

        genres = [g["name"] for g in data.get("genres", [])]

        # Content rating priority: IT → US → first available
        content_rating = None
        ratings = data.get("content_ratings", {}).get("results", [])
        for country in ("IT", "US"):
            for cr in ratings:
                if cr.get("iso_3166_1") == country:
                    content_rating = cr.get("rating")
                    break
            if content_rating:
                break
        if not content_rating and ratings:
            content_rating = ratings[0].get("rating")

        return TVDetails(
            tmdb_id=data["id"], title=data.get("name", ""),
            overview=data.get("overview"), poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            first_air_date=data.get("first_air_date"),
            genres=genres, vote_average=data.get("vote_average"),
            content_rating=content_rating,
        )

    async def get_tv_credits(self, tmdb_id: int) -> list[CastMember]:
        """Get cast and crew for a TV show."""
        data = await self._get(f"/tv/{tmdb_id}/aggregate_credits")
        if not data:
            return []

        members: list[CastMember] = []
        for p in data.get("cast", [])[:15]:
            roles = p.get("roles", [])
            members.append(CastMember(
                id=p["id"], name=p.get("name", ""),
                character=roles[0].get("character") if roles else None,
                job=None, profile_path=p.get("profile_path"), order=p.get("order", 99),
            ))
        for p in data.get("crew", [])[:5]:
            jobs = p.get("jobs", [])
            job = jobs[0].get("job") if jobs else None
            if job in ("Director", "Writer", "Executive Producer", "Creator"):
                members.append(CastMember(
                    id=p["id"], name=p.get("name", ""), character=None,
                    job=job, profile_path=p.get("profile_path"),
                    order=100 + len(members),
                ))
        return members

    # --- Season / Episode ---

    async def get_season_details(
        self, tv_id: int, season_number: int
    ) -> dict | None:
        """Get season-specific details including poster."""
        return await self._get(f"/tv/{tv_id}/season/{season_number}")

    async def get_season_episodes(
        self, tmdb_id: int, season_number: int
    ) -> list[EpisodeInfo]:
        """Get all episodes for a season with thumbnails."""
        data = await self._get(f"/tv/{tmdb_id}/season/{season_number}")
        if not data:
            return []
        return [
            EpisodeInfo(
                episode_number=ep.get("episode_number", 0),
                name=ep.get("name", f"Episode {ep.get('episode_number', '?')}"),
                overview=ep.get("overview"), still_path=ep.get("still_path"),
                air_date=ep.get("air_date"), runtime=ep.get("runtime"),
            )
            for ep in data.get("episodes", [])
        ]

    async def get_episode_details(
        self, tmdb_id: int, season_number: int, episode_number: int
    ) -> EpisodeInfo | None:
        """Get specific episode details from TMDB."""
        ep = await self._get(
            f"/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}"
        )
        if not ep:
            return None
        return EpisodeInfo(
            episode_number=ep.get("episode_number", episode_number),
            name=ep.get("name", f"Episode {episode_number}"),
            overview=ep.get("overview"), still_path=ep.get("still_path"),
            air_date=ep.get("air_date"), runtime=ep.get("runtime"),
        )

    # --- Images (no language filter to get all results) ---

    async def get_episode_images(
        self, tmdb_id: int, season_number: int, episode_number: int
    ) -> list[dict]:
        """Get available still images for a specific episode."""
        data = await self._get(
            f"/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}/images",
            use_language=False,
        )
        return _image_list(data.get("stills", [])) if data else []

    async def get_tv_images(self, tmdb_id: int) -> dict:
        """Get available poster and backdrop images for a TV show."""
        data = await self._get(f"/tv/{tmdb_id}/images", use_language=False)
        if not data:
            return {"posters": [], "backdrops": []}
        return {
            "posters": _image_list(data.get("posters", [])),
            "backdrops": _image_list(data.get("backdrops", [])),
        }

    async def get_season_images(
        self, tmdb_id: int, season_number: int
    ) -> dict:
        """Get available poster images for a specific season."""
        data = await self._get(
            f"/tv/{tmdb_id}/season/{season_number}/images", use_language=False
        )
        if not data:
            return {"posters": []}
        return {"posters": _image_list(data.get("posters", []))}


tmdb_client = TMDBClient()
