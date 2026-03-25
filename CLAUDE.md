# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TLEX is a self-hosted Telegram Media Server. It uses Telegram channels as a persistent storage backend and streams media directly to a Plex-like web UI. The backend is Python/FastAPI, the frontend is Next.js, and there is a native Android TV app.

## Commands

### Backend (Python)

Python dependencies are managed with `uv` (not pip/poetry).

```bash
# Run backend in development mode
uv run uvicorn app.main:app --reload --port 8000

# Lint
uv run ruff check app/

# Format
uv run ruff format app/

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_auth.py

# Run a single test
uv run pytest tests/test_auth.py::test_login
```

### Frontend (Next.js)

```bash
cd frontend

npm run dev       # development server (port 3000)
npm run build     # production build
npm run lint      # ESLint
```

### Docker (Full Stack)

```bash
docker-compose up -d --build    # start all services
docker-compose down             # stop all services
docker logs tlex-cloudflared    # get public tunnel URL
```

## Architecture

### Backend (`app/`)

Entry point is `app/main.py`. The lifespan handler performs startup tasks: create DB tables, load Telegram workers, start background tasks (subtitle cache population, auto-scan scheduler, backup sync scheduler, stream reader cleanup, MTProto keepalive loop).

**Key layers:**
- `app/config.py` — Pydantic-settings; reads from `.env` (and `.env.dev`/`.env.prod` as overrides). Access via `get_settings()` (cached with `@lru_cache`).
- `app/database.py` — SQLAlchemy async engine (asyncpg driver, pool_size=10). DB schema is created at startup via `create_all_tables()` — **no Alembic migrations used**.
- `app/models/` — SQLAlchemy ORM: `media.py` (MediaItem, MediaPart, MediaStream), `user.py` (User, Profile, Watchlist, WatchProgress), `worker.py` (Worker), `backup.py` (BackupChannel, BackupMessage).
- `app/schemas/` — Pydantic v2 request/response models. `app/schemas/__init__.py` re-exports all.
- `app/api/v1/` — FastAPI routers, one file per domain (auth, media, series, seasons, stream, subtitles, scanner, workers, profiles, progress, watchlist, backup, device_auth, people). All mounted under `/api`.
- `app/api/deps.py` — FastAPI dependency injection: `DBSession`, `CurrentUser`, `CurrentUserOptional`.
- `app/core/worker_manager.py` — `WorkerManager` singleton (`worker_manager`). Manages a pool of Pyrogram `Client` objects across multiple Telegram accounts. Premium accounts get 6 clients, standard get 4. Streams acquire clients from the pool and release them on completion.
- `app/services/streaming/` — `VirtualStreamReader` provides a file-like interface over files split across multiple Telegram messages. Handles byte-range seeking, transparent part concatenation, and load balancing across clients.
- `app/services/scanner/` — Scans Telegram channels/topics to populate the media library. Movies detected from filenames; series detected from topic names + S/E patterns.
- `app/services/backup/` — Mixin-based `BackupService`: creates a mirror megagroup, syncs topics/messages, runs health checks, auto-promotes backup to main on failure.
- `app/services/subtitles/` — Extracts subtitles directly from MKV files in Telegram without full download, using EBML parsing + byte-range streaming.
- `app/services/tmdb/` — TMDB API client for metadata, posters, backdrops.
- `app/services/ffmpeg.py`, `ffprobe.py` — Transcoding (remux to browser-compatible container) and media analysis.
- `app/services/scheduler.py` — `auto_scan_scheduler` and `backup_sync_scheduler` as background asyncio tasks.

### Frontend (`frontend/src/`)

Next.js App Router. All authenticated pages live under `app/(main)/` which wraps them with a sidebar layout. The video player page `app/watch/[id]/` is fullscreen with no sidebar.

**Key areas:**
- `components/ds/` — Design System (DSButton, DSCard, DSInput, DSIconButton, DSDatePicker, DSAvatar, etc.). Always use DS components for UI rather than raw HTML or shadcn components directly.
- `components/player/` — Video player orchestrator (`video-player.tsx`) and hooks in `hooks/player/`. Subtitles rendered via `SubtitlesOctopus` (libass-wasm) through `subtitle-renderer.tsx`.
- `lib/api/` — Modular Axios client. `lib/api/client.ts` is the Axios instance with auth token injection. Each domain has its own file (`media.ts`, `series.ts`, `stream.ts`, etc.). `lib/api.ts` re-exports everything for backward compatibility.
- `contexts/auth-context.tsx` — Auth state. `contexts/profile-context.tsx` — Active profile selection.
- `lib/breakpoints.ts` — `BREAKPOINTS` constants + `useIsMobile`/`useBreakpoint` hooks.

**API routing:** `NEXT_PUBLIC_API_URL=""` (empty string) in Docker, so all API calls go through Next.js to the same origin. `BACKEND_URL` (set to `http://backend:8000`) is used server-side only in Next.js route handlers/SSR.

### Android TV (`android-tv/`)

Kotlin + Jetpack Compose + Hilt. Uses Retrofit to talk to the TLEX backend. ExoPlayer/Media3 for playback. Standard MVVM with ViewModels per screen.

## Key Patterns

- **FloodWait handling:** `WorkerManager` automatically rotates to the next available client when a `FloodWait` error occurs, without surfacing it to the user.
- **Auth:** JWT access token (30 min) + refresh token (30 days), stored as cookies on the frontend. The `Accept-Language` header (from `TLEX_LOCALE` cookie) controls TMDB metadata language.
- **DB schema:** `create_all_tables()` at startup handles table creation. For column additions, a migration script in `scripts/` is the pattern.
- **Logging:** Loguru throughout the backend. `setup_logging()` in `app/core/logging.py`.
- **Rate limiting:** slowapi on FastAPI endpoints.
