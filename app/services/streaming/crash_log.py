"""In-memory ring buffer for streaming diagnostics.

Events are accumulated continuously (up to 500 entries). The buffer is
flushed to crash_stream.json ONLY when a critical exception or hang is
detected — never during normal operation, to keep the hot path free of I/O.
"""

import collections
import json
import time
from pathlib import Path

_MAX_ENTRIES = 500
_ring: collections.deque[dict] = collections.deque(maxlen=_MAX_ENTRIES)
_CRASH_LOG_PATH = Path("crash_stream.json")


def record(event: str, **fields) -> None:
    """Append a diagnostic entry to the ring buffer (non-blocking, O(1))."""
    _ring.append({"ts": time.time(), "event": event, **fields})


def flush(reason: str) -> None:
    """Dump the ring buffer to crash_stream.json (call only on crash/hang).

    This is a best-effort write. If the disk write fails, the error is
    silently discarded so it never cascades into the stream pipeline.
    """
    payload = {
        "reason": reason,
        "flushed_at": time.time(),
        "total_entries": len(_ring),
        "entries": list(_ring),
    }
    try:
        _CRASH_LOG_PATH.write_text(json.dumps(payload, indent=2, default=str))
    except OSError:
        pass
