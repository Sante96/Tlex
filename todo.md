# TLEX - Development TODO

---

## ✅ COMPLETED PHASES (0-13)

---

<details>
<summary><b>Phase 0-13: All Phases (click to expand)</b></summary>

- **Phase 0**: Infrastructure (Docker, PostgreSQL, Redis)
- **Phase 1**: Worker Engine (Telegram worker pool, FloodWait handling)
- **Phase 2**: Scanner (Channel scanning, TMDB metadata, FFprobe)
- **Phase 3**: Virtual Streamer (Multi-part file stitching, HTTP Range)
- **Phase 4**: FFmpeg Remuxing (Zero-transcode video, AAC audio)
- **Phase 5**: Subtitles & Fonts (ASS/SRT extraction, font extraction)
- **Phase 6**: Frontend Next.js (Library UI, Video player)
- **Phase 7**: Code Cleanup (Refactoring, deduplication)
- **Phase 8**: Code Modularization (Pydantic schemas)
- **Phase 9**: Plex-Style Redesign (Sidebar, Library grid, Series pages)
- **Phase 10**: SubtitlesOctopus + Snap-to-Keyframe Sync ✅
- **Phase 11**: Security & Auth ✅
  - Auth su endpoints protetti (scanner, media write ops)
  - CORS configurabile (non più wildcard)
  - Refresh tokens con rotation
  - Rate limiting (slowapi)
- **Phase 12**: User Features ✅
  - Watchlist/Favorites (model + API + UI)
  - Settings page (preferenze audio/sottotitoli/riproduzione)
- **Phase 13**: Production Readiness ✅
  - Automated tests (pytest + fixtures)
  - Structured JSON logging per produzione
  - Health check completo (DB, Redis, Workers)
- **Technical Debt**: Scanner modularizzato in package ✅

</details>

---

## 🟠 CURRENT PRIORITY

---

Tutte le fasi principali sono completate! 🎉

### ✅ Per-User Visual Overrides (2026-02-19)
- [x] UserMediaOverride model (user_id + media_item_id → poster_path, backdrop_path)
- [x] UserSeriesOverride model (user_id + series_id → poster_path, backdrop_path, season_posters)
- [x] Override service (overrides.py: get/upsert/apply helpers)
- [x] PATCH /media/{id} → per-user override (was global admin-only)
- [x] PATCH /series/{id} → per-user override (was global admin-only)
- [x] PATCH /series/{id}/season/{num} → per-user season poster override
- [x] GET endpoints merge user overrides on top of TMDB base data
- [x] Tables auto-created via create_all (no migration needed)

### ✅ Feature: Episode Picker + Auto-Play Next Episode (2026-02-20)
- [x] Backend: Added `series_id` to `MediaItemResponse` schema
- [x] Backend: `GET /api/v1/media/{id}/next` endpoint (same season → next season fallback)
- [x] Frontend: `EpisodePicker` overlay (season dropdown, horizontal scroll with edge fades, animated icon)
- [x] Frontend: `NextEpisodeOverlay` (thumbnail, countdown ring, auto-play after 8s)
- [x] Frontend: `useNextEpisode` hook (fetch next, derive visibility at 30s before end, cancel/re-show)
- [x] `AnimatedEpisodes` icon (lines morph + play triangle collapse on toggle)
- [x] Episode navigation via `router.replace` + stream release
- [x] Extracted `useProgressSaving` hook from `video-player.tsx`

### ✅ Refactor: Codebase Cleanup & Modularization (2026-02-19)
- [x] Split `reader.py` (771→231 lines) into 4 modules: reader, download, telegram, manager
- [x] Split `mkv_extractor.py` (814→94 lines) into 4 modules: mkv_extractor, ebml_parser, builders, cluster_reader
- [x] Refactored `tmdb/client.py` (539→289 lines): `_get` helper eliminates httpx boilerplate, `_image_list` helper, consolidated duplicate `_get_season_details`
- [x] Split `subtitle-renderer.tsx` (489→69 lines): extracted `use-subtitle-engine`, `use-canvas-sync`, `subtitle-fetchers`
- [x] Split `player-settings.tsx` (403→269 lines): extracted `settings-items` + `SyncSubmenu`
- [x] Split `settings/page.tsx` (400→299 lines): extracted `use-settings-data` hook
- [x] Fixed progress saving loop in `video-player.tsx` (stabilized useEffect deps with refs)

### ✅ Refactor: Streaming Package Modularization (2026-02-19)
- [x] Split `reader.py` (771 lines) into 4 focused modules:
  - `reader.py` (231 lines) — VirtualStreamReader class, pool mgmt, read_range
  - `download.py` (266 lines) — stream_part() async generator with retry logic
  - `telegram.py` (151 lines) — peer cache, file_id refresh/ensure
  - `manager.py` (112 lines) — reader cache, factory, release, cleanup

### ✅ Stream Client Leak Fix + Pool Status Warning (2026-02-19)
- [x] `_active_streams` counter in VirtualStreamReader to track active read_range calls
- [x] `release_reader` and `_cleanup_stale_readers` respect `_active_streams` (skip if > 0)
- [x] Fix race condition: removed `_cleanup_stale_readers()` from `get_virtual_reader()` (background task handles it)
- [x] `pool_status()` lightweight method on WorkerManager (no DB session)
- [x] `GET /stream/pool-status` endpoint for frontend polling
- [x] Pool info headers in stream response (X-Pool-Total, X-Pool-Available, X-Pool-Pressure, X-Stream-Clients)
- [x] `getPoolStatus` API function + `PoolStatus` type
- [x] `usePoolStatus` hook with polling interval
- [x] `PoolWarningOverlay` component (no_clients = red, high_pressure = yellow)
- [x] Integrated in VideoPlayer (polls every 15s while playing)
- [x] Force-release in `release_reader`: immediate client release when user navigates away, regardless of active streams
- [x] `_force_released` flag: active `_stream_part`/`read_range` bail out immediately after force-release (prevents frozen navigation)

### ✅ Bugfix: Seek Loader & Subtitles (2026-02-19)
- [x] Fix loader spinner stuck after seek (useVideoEvents effect re-ran on isSeeking/streamStartTime change, resetting frame detection)
- [x] Fix subtitles not rendering after seek (enabled prop depended on isLoading, destroying SubtitlesOctopus instance)
- [x] Add INFO-level logs to streaming pipeline ([POOL], [STREAM], [READER], [PLAY], [RAW], [WARM], [FFMPEG])
- [x] Set default log level to INFO (debug=False)

### ✅ Concurrent Streaming (2026-02-04)
- [x] Multi-client per worker account (premium: 4, standard: 2)
- [x] Persistenza sessioni extra in DB (`extra_sessions` JSON)
- [x] Client pool con tracking usage (`_client_in_use`)
- [x] Script migrazione `migrate_extra_sessions.py`
- [x] Fix FFmpeg zombie processes on browser refresh
- [x] Auto-kill previous FFmpeg when new request for same media arrives

### ✅ Phase 14: Plex-Style Visual Overhaul (2026-02-14)
- [x] Sidebar/TopBar semi-transparent con backdrop-blur
- [x] Backdrop image fixed a viewport (dietro sidebar/nav)
- [x] ActionButton glassmorphism (primary glow, secondary glass+blur)
- [x] Logo TMDB ufficiale nel RatingBadge
- [x] Episode cards Plex-style (grid 3 colonne, thumb 16:9, overlay info)
- [x] Season detail hero uniformato (poster stagione, layout verticale)
- [x] Smart "Riproduci" button (prossimo episodio non visto, skip specials)
- [x] Watchlist toggle funzionante su movie detail
- [x] Edit Media Modal (glassmorphism, 4 tabs: Generale/Locandina/Sfondo/Info)
- [x] Backend PATCH /media/{id} + GET /media/{id}/tmdb-images
- [x] Backend PATCH /series/{id} + GET /series/{id}/tmdb-images
- [x] TMDB client: fetch episode stills, TV/season images
- [x] Edit modal su movie, series, episode detail pages
- [x] Season poster editing (JSON override su Series, TMDB image picker)
- [x] Backend PATCH /series/{id}/season/{num} + GET tmdb-images
- [x] Watchlist per serie (series_id su Watchlist, toggle su series detail, watchlist page unificata)
- [x] Breadcrumb dinamico con nomi reali (serie/film) da API
- [x] Gestione utenti in Impostazioni (lista, toggle admin, elimina)
- [x] Hover states migliorati per sidebar/topbar/searchbar

---

## 🟡 NEXT UP (Nice to Have)

---

### Frontend Polish

- [ ] Menu contestuale poster (tre punti)
- [ ] Mobile responsive polish
- [x] Animazioni transizione pagine ✅
- [ ] Testare tag ASS avanzati (karaoke, animazioni)

### Monitoring & Metrics

- [ ] Prometheus metrics endpoint
- [ ] Grafana dashboard
- [ ] Error tracking (Sentry)

### Performance

- [ ] Cache font su filesystem
- [ ] PRE_FETCH - prefetch next chunks during streaming
- [ ] Quality replacement - auto-replace with better quality uploads

---

## 🟢 BACKLOG

---

### Ideas

- [x] Auto-refresh file_id on expiration (transparent to user) ✅
- [x] Auto-scan scheduler (periodic channel scanning) ✅
- [ ] Admin Panel - web-based management interface
- [ ] TMDB image base URL in config
- [ ] FloodWait feedback migliorato

---

## 📝 NOTE

---

### Settings Page (per dopo)

```
Pagina /settings:
- Audio: Lingua predefinita (ITA/ENG/JPN)
- Sottotitoli: Lingua default, on/off di default
- Qualità: Auto / Forza specifica
- Player: Autoplay next episode, Skip intro
- Account: Cambia password, gestione profili
```
