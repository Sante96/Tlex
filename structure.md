# ============================================

# TLEX - Project Structure

# ============================================

# Last updated: 2026-02-19

# Phase: 14 Complete - Plex-Style Visual Overhaul + Edit Modal + Watchlist Series
# + Concurrent Streaming + User Management + Cleanup/Modularization

tlex/
├── 📁 app/ # Main application package
│ ├── **init**.py
│ ├── main.py # FastAPI app entry point
│ ├── config.py # Pydantic Settings configuration
│ ├── database.py # SQLAlchemy async engine & session
│ │
│ ├── 📁 models/ # SQLAlchemy ORM models
│ │ ├── **init**.py
│ │ ├── user.py # User, Profile, Watchlist, WatchProgress models
│ │ ├── worker.py # Telegram Worker model
│ │ └── media.py # MediaItem, MediaPart, MediaStream
│ │
│ ├── 📁 schemas/ # Pydantic request/response models ✅
│ │ ├── **init**.py # Exports all schemas
│ │ ├── auth.py # UserCreate, UserResponse, TokenResponse
│ │ ├── media.py # MediaItemResponse, MediaListResponse, etc.
│ │ ├── profile.py # ProfileCreate, ProfileResponse
│ │ ├── watchlist.py # 🆕 WatchlistMediaResponse (supports series)
│ │ └── scanner.py # ScanRequest, ScanResponse
│ │
│ ├── 📁 api/ # REST API layer
│ │ ├── **init**.py
│ │ ├── v1/
│ │ │ ├── **init**.py # Router aggregation
│ │ │ ├── auth.py # /auth endpoints (JWT login, user management)
│ │ │ ├── scanner.py # /scanner endpoints
│ │ │ ├── media.py # Media library endpoints + PATCH update + TMDB images
│ │ │ ├── profiles.py # 🆕 Profile CRUD + worker assignment
│ │ │ ├── progress.py # Watch progress endpoints
│ │ │ ├── series.py # Series/Season endpoints
│ │ │ ├── stream.py # Streaming endpoints (Phase 3)
│ │ │ ├── subtitles.py # Subtitle extraction (Phase 5)
│ │ │ └── watchlist.py # Watchlist (media + series)
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
│ │ ├── service.py # SubtitleExtractor orchestration
│ │ ├── mkv_extractor.py # Direct MKV extraction orchestrator (slim)
│ │ ├── ebml_parser.py # EBML parsing (tracks, clusters, blocks)
│ │ ├── builders.py # ASS/SRT content builders
│ │ ├── cluster_reader.py # Cluster reading strategies (Cues + fallback)
│ │ ├── cache.py # Subtitle cache management
│ │ ├── fonts.py # Font name extraction
│ │ └── models.py # SubtitleTrack, AttachedFont dataclasses
│ ├── 📁 streaming/ # 🆕 Modular streaming package
│ │ ├── __init__.py # Re-exports VirtualStreamReader, get_virtual_reader, release_reader
│ │ ├── reader.py # VirtualStreamReader class (pool mgmt + read_range)
│ │ ├── download.py # stream_part() async generator with retry logic
│ │ ├── telegram.py # Telegram API: peer cache, file_id refresh/ensure
│ │ ├── manager.py # Reader cache, factory, release, cleanup
│ │ ├── cache.py # Chunk cache + file_id cache
│ │ └── models.py # StreamPosition dataclass
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
│ │ │ │ │ └── [id]/season/[season]/ # Season detail
│ │ │ │ ├── media/[id]/ # Detail page
│ │ │ │ ├── watchlist/ # 🆕 Watchlist page (film + serie)
│ │ │ │ └── settings/ # Settings page
│ │ │ ├── watch/[id]/ # Player (fullscreen, no sidebar)
│ │ │ ├── profiles/ # 🆕 Profile selection (Netflix-style)
│ │ │ ├── login/ # Login page
│ │ │ └── register/ # Register page
│ │ │
│ │ ├── components/
│ │ │ ├── ds/ # 🆕 Design System components
│ │ │ │ ├── index.ts # Exports all DS components
│ │ │ │ ├── action-button.tsx # Glassmorphism action buttons
│ │ │ │ ├── episode-card.tsx # Plex-style episode grid card
│ │ │ │ ├── hero-banner.tsx # Full-page hero with poster
│ │ │ │ ├── detail-page-layout.tsx # Fixed viewport backdrop
│ │ │ │ ├── edit-media-modal.tsx # Edit modal (orchestrator)
│ │ │ │ ├── edit-media-tabs/ # 🆕 Extracted tab components
│ │ │ │ │ ├── index.ts
│ │ │ │ │ ├── field.tsx # Shared field wrapper
│ │ │ │ │ ├── general-tab.tsx # Title/overview/date form
│ │ │ │ │ ├── image-picker-tab.tsx # TMDB image grid picker
│ │ │ │ │ └── info-tab.tsx # Stream info display
│ │ │ │ ├── rating-badge.tsx # TMDB logo + rating
│ │ │ │ ├── meta-row.tsx # Meta info row
│ │ │ │ ├── poster-card.tsx # Poster card with hover
│ │ │ │ ├── cast-section.tsx # Horizontal scrolling cast
│ │ │ │ └── [nav-item, avatar, button, card, input, dropdown...]
│ │ │ ├── ui/ # shadcn/ui + custom
│ │ │ │ ├── avatar-picker.tsx # Modal selezione avatar (Portal)
│ │ │ │ └── [shadcn...]
│ │ │ ├── layout/ # 🆕 Layout components
│ │ │ │ ├── bottom-nav.tsx # 🆕 Mobile bottom navigation bar (md:hidden)
│ │ │ │ ├── sidebar.tsx # hidden md:flex (desktop only)
│ │ │ │ └── top-bar.tsx # Search + user avatar
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
│ │ │ │ ├── video-player.tsx # Main player orchestrator
│ │ │ │ ├── player-controls.tsx # Playback controls bar
│ │ │ │ ├── player-settings.tsx # Dropdown audio/sub/offset
│ │ │ │ ├── settings-items.tsx # MenuItem, SelectItem, SyncSubmenu
│ │ │ │ ├── pool-warning.tsx # Dynamic pool warning overlay
│ │ │ │ ├── animated-icons.tsx # Framer-motion animated SVG icons
│ │ │ │ ├── volume-slider.tsx # YouTube-style volume slider
│ │ │ │ ├── video-seekbar.tsx # Seek bar component
│ │ │ │ ├── subtitle-renderer.tsx # Thin wrapper for SubtitlesOctopus
│ │ │ │ ├── episode-picker.tsx # Episode overlay (season tabs + episode list)
│ │ │ │ ├── next-episode-overlay.tsx # Auto-play next episode countdown overlay
│ │ │ ├── settings/ # 🆕 Settings sub-components
│ │ │ │ ├── index.ts
│ │ │ │ ├── workers-card.tsx
│ │ │ │ ├── stats-card.tsx
│ │ │ │ ├── scanner-card.tsx
│ │ │ │ ├── users-card.tsx # 🆕 User management (admin toggle/delete)
│ │ │ │ ├── add-worker-card.tsx
│ │ │ │ └── change-password-modal.tsx
│ │ │ ├── auth-guard.tsx
│ │ │ └── watchlist-button.tsx
│ │ │
│ │ ├── contexts/
│ │ │ ├── auth-context.tsx
│ │ │ └── profile-context.tsx # 🆕 Profile selection state
│ │ ├── hooks/
│ │ │ ├── use-settings-data.ts # Admin data fetching for settings page
│ │ │ ├── player/ # Player hooks
│ │ │ │ ├── use-player-preferences.ts
│ │ │ │ ├── use-video-sync.ts
│ │ │ │ ├── use-video-events.ts
│ │ │ │ ├── use-video-hotkeys.ts
│ │ │ │ ├── use-pool-status.ts # Pool status polling
│ │ │ │ ├── use-subtitle-engine.ts # SubtitlesOctopus lifecycle + render loop
│ │ │ │ ├── use-canvas-sync.ts # Canvas letterbox sizing + ResizeObserver
│ │ │ │ ├── use-progress-saving.ts # Watch progress periodic + unload saving
│ │ │ │ ├── use-next-episode.ts # Next episode detection + overlay visibility
│ │ │ │ └── subtitle-fetchers.ts # Font + subtitle content fetching
│ │ ├── types/
│ │ │ └── libass-wasm.d.ts # 🆕 TypeScript types for SubtitlesOctopus
│ │ └── lib/
│ │ ├── api.ts # Re-exports (backward compat)
│ │ ├── api/ # 🆕 Modular API client
│ │ │ ├── index.ts # Aggregated exports
│ │ │ ├── client.ts # Axios instance + interceptors
│ │ │ ├── auth.ts # Login, register, getCurrentUser
│ │ │ ├── media.ts # Media CRUD, cast, scanner, update, TMDB images
│ │ │ ├── series.ts # Series, seasons, episodes
│ │ │ ├── watchlist.ts # Watchlist add/remove/check (media + series)
│ │ │ ├── progress.ts # Watch progress, continue watching
│ │ │ ├── profiles.ts # Profile CRUD
│ │ │ ├── stream.ts # Stream URLs, subtitles, pool status, release
│ │ │ └── workers.ts # Workers & system stats
│ │ ├── breakpoints.ts # 🆕 BREAKPOINTS constants + useIsMobile/useBreakpoint hooks
│ │ ├── format.ts # Formatting utilities
│ │ └── utils.ts # General utilities
│ └── public/
│ ├── avatars/ # Profile avatar images (9 PNG)
│ ├── tmdb-logo.svg # 🆕 Official TMDB logo (brand assets)
│ └── lib/ # SubtitlesOctopus WASM files
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
