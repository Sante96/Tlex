# ============================================

# TLEX - Project Structure

# ============================================

# Last updated: 2026-02-04

# Phase: 13 Complete - Security, Watchlist, Settings, Tests, Logging
# + Concurrent Streaming: Multi-client per worker (premium/standard)

tlex/
├── 📁 app/ # Main application package
│ ├── **init**.py
│ ├── main.py # FastAPI app entry point
│ ├── config.py # Pydantic Settings configuration
│ ├── database.py # SQLAlchemy async engine & session
│ │
│ ├── 📁 models/ # SQLAlchemy ORM models
│ │ ├── **init**.py
│ │ ├── user.py # User & Profile models
│ │ ├── worker.py # Telegram Worker model
│ │ └── media.py # MediaItem, MediaPart, MediaStream
│ │
│ ├── 📁 schemas/ # Pydantic request/response models ✅
│ │ ├── **init**.py # Exports all schemas
│ │ ├── auth.py # UserCreate, UserResponse, TokenResponse
│ │ ├── media.py # MediaItemResponse, MediaListResponse, etc.
│ │ ├── profile.py # 🆕 ProfileCreate, ProfileResponse
│ │ └── scanner.py # ScanRequest, ScanResponse
│ │
│ ├── 📁 api/ # REST API layer
│ │ ├── **init**.py
│ │ ├── v1/
│ │ │ ├── **init**.py # Router aggregation
│ │ │ ├── auth.py # /auth endpoints (JWT login)
│ │ │ ├── scanner.py # /scanner endpoints
│ │ │ ├── media.py # Media library endpoints
│ │ │ ├── profiles.py # 🆕 Profile CRUD + worker assignment
│ │ │ ├── progress.py # Watch progress endpoints
│ │ │ ├── series.py # Series/Season endpoints
│ │ │ ├── stream.py # Streaming endpoints (Phase 3)
│ │ │ └── subtitles.py # Subtitle extraction (Phase 5)
│ │ └── deps.py # Dependency injection (get*current_user, get_current_user_optional)
│ │
│ ├── 📁 core/ # Core functionality
│ │ ├── **init**.py
│ │ ├── logging.py # Loguru configuration
│ │ ├── security.py # JWT, password hashing
│ │ ├── utils.py # Utility functions (utc_now, find_ffmpeg)
│ │ └── worker_manager.py # Telegram Worker Pool (Phase 1)
│ │
│ └── 📁 services/ # Business logic services
│ ├── **init**.py
│ ├── 📁 scanner/ # 🆕 Modular scanner package
│ │ ├── **init**.py # Re-exports scanner_service
│ │ ├── models.py # ScannedFile, MediaGroup dataclasses
│ │ ├── telegram.py # TelegramScanner class
│ │ ├── processor.py # Media processing logic
│ │ └── service.py # ScannerService orchestration
│ ├── 📁 tmdb/ # 🆕 Modular TMDB package
│ │ ├── **init**.py
│ │ ├── client.py
│ │ └── models.py
│ ├── 📁 subtitles/ # 🆕 Modular subtitles package
│ │ ├── **init**.py
│ │ ├── service.py
│ │ ├── fonts.py
│ │ └── models.py
│ ├── 📁 streaming/ # 🆕 Modular streaming package
│ │ ├── **init**.py
│ │ ├── reader.py
│ │ ├── cache.py
│ │ └── models.py
│ ├── ffprobe.py # FFprobe media analysis ✅
│ ├── mkv_cues.py # MKV Cues parser for keyframe extraction
│ └── ffmpeg.py # FFmpeg remux pipeline ✅
│
├── 📁 scripts/ # CLI utilities
│ ├── create_tables.py # Initialize database
│ ├── add_worker.py # Add Telegram worker account
│ ├── migrate_profiles.py # Manual DB migration for profiles
│ └── migrate_extra_sessions.py # 🆕 Add extra_sessions column for concurrent streams
│
├── 📁 tests/ # Test suite
│ ├── **init**.py
│ ├── conftest.py # Pytest fixtures
│ └── test*\*.py
│
├── 📁 frontend/ # Next.js Frontend (Plex-style redesign)
│ ├── src/
│ │ ├── app/ # App Router pages
│ │ │ ├── (main)/ # 🆕 Route group with sidebar layout
│ │ │ │ ├── layout.tsx # Main layout (sidebar + content)
│ │ │ │ ├── page.tsx # Home/Dashboard
│ │ │ │ ├── movies/ # Movies library grid
│ │ │ │ ├── series/ # Series library grid  
│ │ │ │ ├── media/[id]/ # Detail page
│ │ │ │ └── settings/ # Settings page
│ │ │ ├── watch/[id]/ # Player (fullscreen, no sidebar)
│ │ │ ├── profiles/ # 🆕 Profile selection (Netflix-style)
│ │ │ ├── login/ # Login page
│ │ │ └── register/ # Register page
│ │ │
│ │ ├── components/
│ │ │ ├── ui/ # shadcn/ui + custom
│ │ │ │ ├── profile-avatar.tsx # 🆕 Avatar con bordo colorato
│ │ │ │ ├── avatar-picker.tsx # 🆕 Modal selezione avatar (Portal)
│ │ │ │ └── [shadcn...]
│ │ │ ├── layout/ # 🆕 Layout components
│ │ │ │ ├── sidebar.tsx # Sidebar laterale
│ │ │ │ ├── top-bar.tsx # Search + user avatar
│ │ │ │ └── main-layout.tsx
│ │ │ ├── library/ # 🆕 Library components
│ │ │ │ ├── library-grid.tsx # Grid di poster
│ │ │ │ ├── library-header.tsx # Filtri, sort
│ │ │ │ └── media-poster.tsx # Card Plex-style
│ │ │ ├── media/ # 🆕 Detail page components
│ │ │ │ ├── detail-hero.tsx
│ │ │ │ ├── detail-actions.tsx
│ │ │ │ └── detail-metadata.tsx
│ │ │ ├── profiles/ # 🆕 Profile modals (refactored)
│ │ │ │ ├── index.ts
│ │ │ │ ├── create-profile-modal.tsx
│ │ │ │ └── edit-profile-modal.tsx
│ │ │ ├── player/ # Player components
│ │ │ │ ├── video-player.tsx
│ │ │ │ ├── player-controls.tsx
│ │ │ │ ├── player-settings.tsx # Dropdown audio/sub/offset
│ │ │ │ └── subtitle-renderer.tsx # SubtitlesOctopus (Detached Mode)
│ │ │ ├── auth-guard.tsx
│ │ │ └── [legacy...] # Da rimuovere dopo migrazione
│ │ │
│ │ ├── contexts/
│ │ │ ├── auth-context.tsx
│ │ │ └── profile-context.tsx # 🆕 Profile selection state
│ │ ├── hooks/
│ │ │ ├── player/ # 🆕 Player hooks
│ │ │ │ ├── use-player-preferences.ts
│ │ │ │ ├── use-video-sync.ts
│ │ │ │ ├── use-video-events.ts
│ │ │ │ └── use-video-hotkeys.ts
│ │ ├── types/
│ │ │ └── libass-wasm.d.ts # 🆕 TypeScript types for SubtitlesOctopus
│ │ └── lib/
│ │ ├── api.ts # Re-exports (backward compat)
│ │ ├── api/ # 🆕 Modular API client
│ │ │ ├── index.ts # Aggregated exports
│ │ │ ├── client.ts # Axios instance + interceptors
│ │ │ ├── auth.ts # Login, register, getCurrentUser
│ │ │ ├── media.ts # Media CRUD, cast, scanner
│ │ │ ├── series.ts # Series, seasons, episodes
│ │ │ ├── progress.ts # Watch progress, continue watching
│ │ │ ├── profiles.ts # Profile CRUD
│ │ │ └── stream.ts # Stream URLs, subtitles
│ │ ├── format.ts # Formatting utilities
│ │ └── utils.ts # General utilities
│ └── public/
│ ├── avatars/ # 🆕 Profile avatar images (9 PNG)
│ └── lib/ # 🆕 SubtitlesOctopus WASM files
│
├── 📁 docs/ # Documentation
│ └── cloudflare-setup.md # Cloudflare Tunnel guide
│
├── 📁 data/ # Docker volumes (gitignored)
│ ├── postgres/
│ ├── redis/
│ └── pgadmin/
│
├── .env # Environment variables (gitignored)
├── .env.example # Environment template
├── .gitignore
├── docker-compose.yml # Infrastructure services
├── pyproject.toml # Python project config & deps
├── README.md # Project documentation
├── roadmap.md # Development phases
└── structure.md # This file
