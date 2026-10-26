"""Concert topics: "Concerti · <anime/game>" in the group holds that franchise's concerts.

The topic names the franchise, so nothing is guessed from file names. Only the franchise
is looked up on TMDB (anime are there, games often aren't); a concert never is: it
would come back as some film or episode of the same name.
"""

import re
from datetime import date

from loguru import logger
from pyrogram import Client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media import Franchise, MediaItem, MediaType
from app.services.scanner.models import MediaGroup
from app.services.scanner.processor import add_parts, already_scanned, analyze_streams
from app.services.tmdb import tmdb_client

_CONCERT_TOPIC = re.compile(r"^\s*concerti\s*[·•・|\-–—:]\s*(?P<name>\S.*?)\s*$", re.IGNORECASE)
_VIDEO_EXTENSION = re.compile(r"\.(mkv|mp4|avi|webm)$", re.IGNORECASE)
_TAGS = re.compile(r"\[[^\]]*\]")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def concert_franchise_name(topic_name: str | None) -> str | None:
    """The anime/game of a "Concerti · <name>" topic (also •, ・, |, -, –, :), else None."""
    match = _CONCERT_TOPIC.match(topic_name or "")
    return match.group("name") if match else None


def franchise_key(name: str) -> str:
    """How scans find a franchise again: its topic name, case and spacing aside."""
    return " ".join(name.casefold().split())


def concert_title(base_name: str) -> tuple[str, int | None]:
    """The file name as a title, and the year in it.

    Not guessit: it ends the title at the year ("Genshin Concert 2023 Melodies of an
    Endless Journey" became "Genshin Concert").
    """
    name = _TAGS.sub(" ", _VIDEO_EXTENSION.sub("", base_name))
    title = " ".join(re.sub(r"[._]", " ", name).split())
    year = _YEAR.search(title)
    return title, int(year.group()) if year else None


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


async def get_or_create_franchise(session: AsyncSession, name: str) -> Franchise:
    """The franchise of this topic name, created (with TMDB's art if it knows it) if new."""
    key = franchise_key(name)
    franchise = (
        await session.execute(select(Franchise).where(Franchise.key == key))
    ).scalar_one_or_none()
    if franchise:
        return franchise

    franchise = Franchise(key=key, title=name)
    found = await tmdb_client.search_tv(name)
    # TMDB's first hit for a game is often an unrelated show: keep it only when its title
    # starts with the name's words ("Arknights" → "Arknights: Prelude to Dawn", but not
    # "Fate" → "Fated to Love You")
    words = _words(name)
    if found and words and _words(found.title)[: len(words)] == words:
        franchise.tmdb_id = found.tmdb_id
        franchise.overview = found.overview
        franchise.poster_path = found.poster_path
        franchise.backdrop_path = found.backdrop_path
    session.add(franchise)
    await session.flush()
    logger.info(f"New concert franchise: {name} (TMDB {franchise.tmdb_id})")
    return franchise


async def process_concert_group(
    session: AsyncSession,
    group: MediaGroup,
    client: Client | None,
    franchise_name: str,
) -> MediaItem | None:
    """A concert from the files of a concert topic; None if it was scanned already."""
    if await already_scanned(session, group.files[0]):
        logger.debug(f"Skipping existing: {group.base_name}")
        return None

    franchise = await get_or_create_franchise(session, franchise_name)
    title, year = concert_title(group.base_name)
    concert = MediaItem(
        title=title,
        media_type=MediaType.CONCERT,
        franchise_id=franchise.id,
        release_date=date(year, 1, 1) if year else None,
    )
    session.add(concert)
    await session.flush()

    add_parts(session, concert, group.files)
    # Tracks and chapters (the songs), as for any title
    if client:
        await analyze_streams(session, concert, group.files[0], client)

    await session.commit()
    logger.debug(f"Created concert: {title} ({len(group.files)} parts)")
    return concert
