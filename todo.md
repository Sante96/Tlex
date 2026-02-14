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

### ✅ Concurrent Streaming (2026-02-04)
- [x] Multi-client per worker account (premium: 4, standard: 2)
- [x] Persistenza sessioni extra in DB (`extra_sessions` JSON)
- [x] Client pool con tracking usage (`_client_in_use`)
- [x] Script migrazione `migrate_extra_sessions.py`
- [x] Fix FFmpeg zombie processes on browser refresh
- [x] Auto-kill previous FFmpeg when new request for same media arrives

---

## 🟡 NEXT UP (Nice to Have)

---

### Frontend Polish

- [ ] Menu contestuale poster (tre punti)
- [ ] Mobile responsive polish
- [ ] Animazioni transizione pagine
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
