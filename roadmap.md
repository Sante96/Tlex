# 📽️ Project Blueprint: Telegram Media Server (The "Plex-Killer")

## 1. Project Manifesto

**Goal:** Build a self-hosted, high-performance streaming platform that leverages **Telegram** as an unlimited, zero-cost storage backend.
**UX Target:** Seamless Netflix/Plex experience with metadata, profiles, and instant playback.
**Key Constraints:**

- Respect Telegram API limits (FloodWait handling).
- Bypass the 4GB file limit via "Virtual Concatenation".
- Zero transcoding for video (Remux only) to run on low-end hardware.
- Client-side subtitle rendering (ASS/SSA) to preserve CPU.
- **Forum/Topic Support**: Scan specific topics within Telegram forum channels for organized media libraries.

---

## 2. Technology Stack & Infrastructure

### 🛠️ Core Stack

- **Language:** Python 3.11+
- **Package Manager:** **uv** (Ultra-fast Pip replacement).
- **Web Framework:** **FastAPI** (Async, High performance).
- **Telegram Engine:** **Pyrogram** (Async MTProto client).
- **Database:** **PostgreSQL 15** (via SQLAlchemy Async).
- **Cache & Locks:** **Redis** (Essential for stream chunks and worker coordination).
- **Frontend:** **Next.js 14+** (App Router), TailwindCSS, Shadcn/UI.
- **Player Engine:** HTML5 Video + **JavascriptSubtitlesOctopus** (WASM).

### 🏗️ Infrastructure (Hybrid Strategy)

- **Development:**
  - Local Machine: Run Python code via `uv run`.
  - Services: Run PostgreSQL, Redis, and Cloudflared via Docker Compose.
- **Production:** Full Docker Compose stack.
- **Remote Access:** **Cloudflare Tunnel** (`cloudflared`) to expose the app via HTTPS without opening router ports.

---

## 2.5 Topic & Storage Strategy

**Concept:** Usage of a **Private Telegram Channel with "Topics" enabled (Forum Mode)** to mimic a file system structure.

### 📂 Channel Structure

- **The Library Channel:** A single private channel where the Bot/Workers are admins.
- **Forum Mode:** MUST be enabled to support Topics (`message_thread_id`).

### 📂 Topic Organization Logic

The Scanner Service must distinguish content based on the `topic_id` (`message_thread_id`) where the file is found:

#### Type A: The "Movies Archive" (Bucket Strategy)

- **Structure:** A single Topic named `Movies Archive` (Fixed ID configured in `.env`).
- **Content:** Contains ALL movie files mixed together (`Matrix.mkv`, `Avatar.mkv`).
- **Scanner Logic:** If a file is found in this `topic_id`:
  - Treat it strictly as a **Movie**.
  - Use `guessit` on the filename to extract the TMDB query.

#### Type B: "TV Series" (Folder Strategy)

- **Structure:** One Topic per TV Show.
- **Naming Convention:** Topic Name = `Series Name` (e.g., Topic "Breaking Bad", Topic "The Office").
- **Content:** Contains all episodes (`S01E01.mkv`, `S01E02.mkv`) of that specific show.
- **Scanner Logic:** If a file is found in ANY topic that is NOT the "Movies Archive":
  - Treat it as an **Episode**.
  - **Hint:** Use the _Topic Name_ as the primary Series Name for the search (fallback to filename parsing if ambiguous).
  - This solves the issue of generic filenames like `Episode 1.mkv` by using the Topic Name as context.

### 📂 Database Mapping

The `media_parts` table MUST store the location coordinates to allow the Worker to download the correct message:

- `channel_id`: The ID of the main library channel.
- `topic_id` (or `message_thread_id`): The ID of the specific topic (Movie Bucket or Series Folder).
- `message_id`: The ID of the file message.

---

## 3. Database Schema (The Truth Source)

### `users`

- `id`: Integer (PK)
- `email`: String (Unique)
- `password_hash`: String
- `is_admin`: Boolean

### `profiles`

- `id`: Integer (PK)
- `user_id`: FK(`users.id`)
- `name`: String
- `avatar_url`: String
- `preferences`: JSON (e.g., `{ "default_audio": "ita", "auto_quality": true }`)

### `workers` (The Telegram Account Pool)

- `id`: Integer (PK)
- `session_string`: Text (Pyrogram Session)
- `phone_number`: String
- `is_premium`: Boolean (Critical for speed)
- `max_concurrent_streams`: Integer (Default: 10 for Premium, 1 for Standard)
- `current_load`: Integer
- `status`: Enum(`ACTIVE`, `FLOOD_WAIT`, `OFFLINE`)
- `flood_wait_until`: Datetime (Nullable)

### `media_items` (The Movie/Episode)

- `id`: Integer (PK)
- `tmdb_id`: Integer
- `title`: String
- `overview`: Text
- `poster_path`: String
- `backdrop_path`: String
- `release_date`: Date
- `media_type`: Enum(`MOVIE`, `EPISODE`)
- `duration_seconds`: Integer

### `media_parts` (Virtual File System)

_Handles files split due to the 4GB limit (e.g., Matrix.mkv.001, Matrix.mkv.002)._

- `id`: Integer (PK)
- `media_item_id`: FK(`media_items.id`)
- `telegram_file_id`: String (The download reference)
- `part_index`: Integer (Order: 0, 1, 2...)
- `start_byte`: BigInteger (Global offset start)
- `end_byte`: BigInteger (Global offset end)
- `file_size`: BigInteger

### `media_streams` (Technical Metadata)

_Used for pre-selection of tracks in the UI._

- `id`: Integer (PK)
- `media_item_id`: FK(`media_items.id`)
- `stream_index`: Integer (FFmpeg index)
- `codec_type`: Enum(`VIDEO`, `AUDIO`, `SUBTITLE`)
- `codec_name`: String (e.g., `h264`, `aac`, `ass`)
- `language`: String (ISO code)
- `is_default`: Boolean

---

## 4. Implementation Phases

### 🟢 Phase 0: Environment & Infra

1.  **Init:** `uv init telegram-media-server`.
2.  **Docker Compose:** Create `docker-compose.yml` containing:
    - `postgres` (Volume: `./data/postgres`)
    - `redis` (Volume: `./data/redis`)
    - `pgadmin` (Port: 5050)
    - `cloudflared` (Command: `tunnel run --token ...`)
3.  **Env:** `.env` file with `API_ID`, `API_HASH`, `DB_URL`, `JWT_SECRET`, `TMDB_API_KEY`.

- **⚠️ Windows Note:** Se hai PostgreSQL locale, usa porta `5433` in docker-compose per evitare conflitti.

### 🟢 Phase 1: The Worker Engine (The Brain)

Create a `WorkerManager` class that handles the connection pool.

- **Logic:**
  - Load all sessions from DB on startup.
  - **`get_best_worker()`**: Algorithm that selects a worker based on:
    1.  Status != `FLOOD_WAIT`
    2.  Priority: Premium > Standard
    3.  Load: Lowest `current_load`
  - **Rescue System:** If a download fails with `FloodWaitError`:
    1.  Mark current worker as `FLOOD_WAIT` in DB.
    2.  Instantaneously retrieve a new worker from the pool.
    3.  Retry the chunk download transparently.

### 🟢 Phase 2: Ingest & Scanner

Create a background service (`scanner.py`) to monitor Telegram Topics.

- **Input:** List of Channel IDs and Topic IDs (e.g., "Movies Archive").
- **Processing:**
  1.  Detect video files (`.mkv`, `.mp4`) or split parts (`.001`).
  2.  **Grouping:** If split files, group them into one `media_item` with multiple `media_parts`.
  3.  **Metadata:** Parse filename (`guessit`) -> Fetch details from TMDB.
  4.  **Analysis:** Run `ffprobe` (via subprocess) on the file to populate `media_streams`.
- **Current Implementation:**
  - Downloads file temporarily to run ffprobe locally.
  - Cleans up temp file after analysis.
- **⚠️ Future Optimization:**
  - Download only MKV header bytes (~1MB) instead of full file for large files.
  - Or use streaming proxy from Phase 3 to provide HTTP URL to ffprobe.

### 🟢 Phase 3: The Virtual Streamer (The Core)

This is the most critical backend component.

- **Class `VirtualStreamReader`:**
  - Input: `media_item_id`, `requested_byte_offset`.
  - **Logic:**
    1.  Identify which `media_part` contains the `requested_byte_offset`.
    2.  Calculate `local_offset` (Request - Part.Start).
    3.  Stream bytes from Telegram via WorkerManager.
    4.  **Boundary Handling:** If the request crosses from Part 1 to Part 2, seamlessly close connection to Part 1 and open Part 2, stitching bytes together.
- **Endpoint `/api/v1/stream/raw/{id}`:**
  - Acts as a local HTTP Proxy.
  - Accepts `Range` headers (crucial for seeking).
  - HEAD request support for metadata.
  - Feeds data into FFmpeg.
- **Current Implementation:**
  - Uses `pyrogram.stream_media()` for chunked downloads.
  - Automatic worker acquisition/release per stream.
  - AsyncIterator pattern for memory efficiency.

### 🟢 Phase 4: FFmpeg Remuxing Pipeline

The API endpoint that feeds the frontend.

- **Command Generation:**
  ```bash
  ffmpeg -ss {start_time} -i http://localhost:8000/api/v1/stream/raw/{id} \
  -map 0:v:{video_idx} -c:v copy \
  -map 0:a:{audio_idx} -c:a aac -b:a 192k \
  -movflags frag_keyframe+empty_moov+faststart \
  -f mp4 -
  ```
- **Features:**
  - **Zero CPU Video:** Uses `-c:v copy`.
  - **Audio Transcode:** Converts DTS/AC3 to AAC (Browser compatible).
  - **Pipe:** Streams output directly to the HTTP Response.
- **Endpoint `/api/v1/stream/play/{id}`:**
  - Query params: `audio`, `video`, `t` (seek time)
  - Returns `video/mp4` with fragmented MP4
- **Current Implementation:**
  - Async subprocess with stdout pipe streaming.
  - Graceful cancellation handling.
  - 64KB chunks for efficient memory usage.

### 🟢 Phase 5: Subtitles & Font Extraction

- **Endpoint `/api/v1/subtitles/{id}`:**
  - Query params: `track`, `format` (ass/srt)
  - Extracts the requested subtitle track.
  - Converts SRT to ASS if needed.
- **Endpoint `/api/v1/subtitles/{id}/tracks`:**
  - Lists available subtitle tracks from DB.
- **Endpoint `/api/v1/subtitles/{id}/fonts`:**
  - Lists attached fonts from MKV container.
- **Endpoint `/api/v1/subtitles/{id}/font/{filename}`:**
  - Downloads specific font file.
- **Current Implementation:**
  - FFmpeg subprocess for extraction.
  - Temp file approach for font extraction.
  - Cache headers for font responses (7 days).
- **⚠️ Future Optimization:**
  - Cache extracted fonts in Redis/filesystem.
  - Batch font extraction to avoid repeated processing.

### 🟢 Phase 6: Frontend (Next.js) & Player

- **Auth:** JWT based login -> Profile Selection.
- **Library UI:** Netflix-style rows (Trending, Continue Watching).
- **The Player Component:**
  - **Video:** `<video src="/api/stream?audio=2">`
  - **Subtitles:** Integrate **JavascriptSubtitlesOctopus**.
    - Load `.wasm` from `/public/lib/`.
    - Overlay `<canvas>` on top of video.
    - Feed the `.ass` URL from Phase 5.
  - **Controls:** Custom UI to switch Audio/Subs (triggering a video reload for Audio, instant update for Subs).

### 🟢 Phase 7: Code Cleanup (COMPLETED)

- **Removed Duplicates:**
  - `get_db()` consolidated to `deps.py` only
  - `find_ffmpeg()` / `find_ffprobe()` extracted to `core/utils.py`
  - `download_chunk()` removed (unused)
- **Consolidated:**
  - `_refresh_file_id()` logic in `virtual_stream.py`
  - `probe_telegram_file()` → `analyze_from_telegram()`
- **Fixed:**
  - Telegram seek: now uses native chunk offset (not downloading from start)
  - Multi-part duration estimation from bitrate

### 🟢 Phase 8: Modularization (COMPLETED)

- **Created `app/schemas/`:**
  - `auth.py` - UserCreate, UserResponse, TokenResponse
  - `media.py` - MediaItemResponse, MediaListResponse, etc.
  - `scanner.py` - ScanRequest, ScanResponse
- **Updated all API endpoints to use centralized schemas**

### 🟢 Phase 9: Plex-Style Redesign (COMPLETED)

- [x] Sidebar navigation (collapsible)
- [x] Library grid with poster cards
- [x] Detail pages for movies and series
- [x] Season/Episode navigation
- [x] Responsive design

### 🟢 Phase 10: User Experience (COMPLETED)

- [x] **Continue Watching** - Watch progress tracking with resume
- [x] **Series/Season grouping** - Proper episode organization
- [x] **Profile Management** - Netflix-style multi-profile system
  - [x] Backend API with dedicated worker per profile
  - [x] Profile selection page
  - [x] Avatar picker (9 images)
  - [x] Profile deletion with confirmation
- [x] **SubtitlesOctopus** - Client-side ASS rendering with WASM
  - [x] Canvas overlay integration
  - [x] Font loading from API
  - [ ] Test advanced ASS tags (karaoke, animations)
- [x] **Episode cards redesign** - Watch progress bars, modern UI

---

## 🔜 Future Phases

### � Phase 11: Security & Auth (COMPLETED)

- [x] Add auth requirement to `/scanner` (admin only), `/media` write ops (admin only)
- [x] Restrict CORS (configurable `CORS_ALLOWED_ORIGINS`)
- [x] Implement refresh tokens (DB storage, rotation, revocation)
- [x] Add rate limiting (slowapi: 5/min auth, 60/min API)

### � Phase 12: User Features (COMPLETED)

- [x] Watchlist/Favorites (model + API + UI)
- [x] Settings page (audio/subtitle preferences, autoplay)
- [x] Cache subtitles/fonts (filesystem) - già implementato in subtitles.py

### 🟢 Phase 13: Production Readiness (COMPLETED)

- [x] Automated tests (pytest + fixtures for auth, watchlist, media)
- [x] Structured logging (JSON for production, colored for dev)
- [x] Health check: verify DB, Redis, Workers status with detailed response
- [x] Prometheus metrics (`/metrics` endpoint)
- [x] Error handling consistency (TLEXException + global handler)

### 🟢 Technical Debt (COMPLETED)

- [x] Split `scanner.py` into modules (`scanner/models.py`, `telegram.py`, `processor.py`, `service.py`)
- [x] Removed duplicate `_get_season_details_standalone` from tmdb.py
- [x] Backend cleanup and code review
- [x] Move TMDB image base URL to config (`tmdb_image_base_url`)
- [x] Improve worker FloodWait feedback (`/workers/status` endpoint)

### 💡 Ideas (Backlog)

- [ ] Auto-refresh file_id on expiration (transparent to user)
- [ ] PRE_FETCH - prefetch next chunks during streaming
- [ ] Admin Panel - web-based management interface
- [ ] Mobile app (React Native / Expo)
- [ ] TV app (React Native / Expo)
- [ ] **Dynamic Client Scaling** - Start with 1 client per stream, monitor throughput, auto-add clients when load > 85%, remove when stable. Optimizes resource usage while maximizing performance.

---

## 5. Deployment & Operations

1.  **First Run:**
    - `docker-compose up -d db redis`
    - `uv run scripts/create_tables.py`
2.  **Adding Workers:**
    - Run CLI tool: `uv run scripts/add_worker.py`
    - Follow prompts to login via Phone/Code.
    - Script detects Premium status automatically.
3.  **Cloudflare Setup:**
    - `cloudflared tunnel login`
    - Copy token to `.env` or docker command.
4.  **Run:**
    - Backend: `uv run uvicorn main:app --host 0.0.0.0 --port 8000`
    - Frontend: `npm start`
