"""Read app version from frontend/package.json (single source of truth)."""

import json
from pathlib import Path


def _read_version() -> str:
    try:
        pkg = Path(__file__).parent.parent / "frontend" / "package.json"
        return json.loads(pkg.read_text(encoding="utf-8"))["version"]
    except Exception:
        return "0.0.0"


__version__ = _read_version()
