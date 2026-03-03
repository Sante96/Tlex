"""People API - person details + their works in the local catalog."""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.deps import DBSession
from app.models.media import MediaItem, MediaType, Series
from app.services.tmdb import tmdb_client

router = APIRouter(prefix="/people", tags=["people"])


@router.get("/{person_id}")
async def get_person(request: Request, session: DBSession, person_id: int) -> dict:
    """Get person info and all their TMDB credits, flagging which are in the local catalog."""
    lang = request.headers.get("Accept-Language", "it-IT")
    person = await tmdb_client.get_person(person_id, language=lang)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Deduplicate credits by tmdb_id (prefer cast role over crew)
    credit_map: dict[int, dict] = {}
    for credit in person["credits"]:
        tmdb_id = credit.get("id")
        media_type = credit.get("media_type")
        if not tmdb_id or media_type not in ("movie", "tv"):
            continue
        if tmdb_id not in credit_map:
            credit_map[tmdb_id] = {
                "tmdb_id": tmdb_id,
                "media_type": media_type,
                "title": credit.get("title") or credit.get("name", ""),
                "poster_path": credit.get("poster_path"),
                "release_date": credit.get("release_date") or credit.get("first_air_date"),
                "character": credit.get("character"),
                "job": credit.get("job"),
                "in_catalog": False,
                "catalog_id": None,
                "catalog_type": None,
            }

    movie_tmdb_ids = [v["tmdb_id"] for v in credit_map.values() if v["media_type"] == "movie"]
    tv_tmdb_ids = [v["tmdb_id"] for v in credit_map.values() if v["media_type"] == "tv"]

    # Match movies in local catalog
    if movie_tmdb_ids:
        q = select(MediaItem).where(
            MediaItem.tmdb_id.in_(movie_tmdb_ids),
            MediaItem.media_type == MediaType.MOVIE,
        )
        result = await session.execute(q)
        for item in result.scalars().all():
            if item.tmdb_id in credit_map:
                credit_map[item.tmdb_id]["in_catalog"] = True
                credit_map[item.tmdb_id]["catalog_id"] = item.id
                credit_map[item.tmdb_id]["catalog_type"] = "media"
                credit_map[item.tmdb_id]["poster_path"] = item.poster_path or credit_map[item.tmdb_id]["poster_path"]

    # Match TV series in local catalog
    if tv_tmdb_ids:
        q = select(Series).where(Series.tmdb_id.in_(tv_tmdb_ids))
        result = await session.execute(q)
        for series in result.scalars().all():
            if series.tmdb_id in credit_map:
                credit_map[series.tmdb_id]["in_catalog"] = True
                credit_map[series.tmdb_id]["catalog_id"] = series.id
                credit_map[series.tmdb_id]["catalog_type"] = "series"
                credit_map[series.tmdb_id]["poster_path"] = series.poster_path or credit_map[series.tmdb_id]["poster_path"]

    works = sorted(credit_map.values(), key=lambda w: w.get("release_date") or "", reverse=True)

    return {
        "id": person["id"],
        "name": person["name"],
        "biography": person["biography"],
        "birthday": person["birthday"],
        "place_of_birth": person["place_of_birth"],
        "profile_path": person["profile_path"],
        "imdb_id": person["imdb_id"],
        "instagram_id": person["instagram_id"],
        "twitter_id": person["twitter_id"],
        "works": list(works),
    }
