"""Streaming chunk cache."""

import time

# Pyrogram uses 1MB chunks for streaming
PYROGRAM_CHUNK_SIZE = 1024 * 1024  # 1MB

# Cache for refreshed file_ids: (part_id, id(client)) -> (file_id, refreshed at)
# Avoids refreshing file_id on every HTTP request
FILE_ID_CACHE: dict[tuple[int, int], tuple[str, float]] = {}
FILE_ID_CACHE_TTL = 30 * 60  # 30 minutes

# Chunk cache for pre-fetched data
# LRU-style cache to avoid re-downloading chunks
_CHUNK_CACHE: dict[tuple[int, int], tuple[bytes, float]] = {}
_CHUNK_CACHE_TTL = 60
_CHUNK_CACHE_MAX_SIZE = 50


def get_cached_chunk(part_id: int, chunk_index: int) -> bytes | None:
    """Get a chunk from cache if available and not expired."""
    key = (part_id, chunk_index)
    if key in _CHUNK_CACHE:
        data, timestamp = _CHUNK_CACHE[key]
        if time.time() - timestamp < _CHUNK_CACHE_TTL:
            return data
        del _CHUNK_CACHE[key]
    return None


def invalidate_file_id_cache(part_id: int, client_id: int | None = None) -> None:
    """
    Invalidate cached file_id for a part (e.g., after FileReferenceExpired).

    Args:
        part_id: The part ID to invalidate
        client_id: If provided, only invalidate for this specific client
    """
    if client_id is not None:
        FILE_ID_CACHE.pop((part_id, client_id), None)
    else:
        for key in [k for k in FILE_ID_CACHE if k[0] == part_id]:
            del FILE_ID_CACHE[key]


def cache_chunk(part_id: int, chunk_index: int, data: bytes) -> None:
    """Cache a chunk, evicting old entries if needed."""
    now = time.time()
    expired = [k for k, (_, ts) in _CHUNK_CACHE.items() if now - ts > _CHUNK_CACHE_TTL]
    for k in expired:
        del _CHUNK_CACHE[k]

    while len(_CHUNK_CACHE) >= _CHUNK_CACHE_MAX_SIZE:
        oldest_key = min(_CHUNK_CACHE.keys(), key=lambda k: _CHUNK_CACHE[k][1])
        del _CHUNK_CACHE[oldest_key]

    _CHUNK_CACHE[(part_id, chunk_index)] = (data, now)
