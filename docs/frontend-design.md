# TLEX Frontend - Plex-Style Design

## Stato Attuale (Netflix-like)

- ❌ Navbar top orizzontale
- ❌ Hero section grande con backdrop
- ❌ Rows orizzontali scrollabili
- ❌ Cards solo poster (aspect 2:3)
- ❌ Colori rosso/nero

## Target: Plex-Style UI

### 🎨 Design System

**Colori:**

- Background: `#1f1f1f` (più grigio di Netflix)
- Sidebar: `#282828`
- Accent: `#e5a00d` (arancione Plex)
- Text primary: `#ffffff`
- Text secondary: `#a0a0a0`
- Card hover: `#333333`

**Typography:**

- Font: Inter o system-ui
- Titoli: Bold, grandi
- Metadata: Small, muted

---

### 📐 Layout Structure

```
┌─────────────────────────────────────────────────────┐
│ [Sidebar]  │         [Main Content Area]            │
│            │                                        │
│ 🏠 Home    │  ┌─────────────────────────────────┐  │
│ 🎬 Movies  │  │  Search Bar + User Avatar       │  │
│ 📺 Series  │  └─────────────────────────────────┘  │
│ ⭐ Watchlist│                                       │
│            │  [Library Grid / Detail View]         │
│ ───────────│                                        │
│ 📁 Libraries│                                       │
│   └ Telegram│                                       │
│            │                                        │
│ ───────────│                                        │
│ ⚙️ Settings │                                        │
└─────────────────────────────────────────────────────┘
```

---

### 📁 Componenti da Creare/Modificare

#### 1. Layout (Priority: HIGH)

- [ ] `sidebar.tsx` - Sidebar laterale fissa
- [ ] `main-layout.tsx` - Layout wrapper con sidebar
- [ ] `top-bar.tsx` - Barra superiore con search + user

#### 2. Library View (Priority: HIGH)

- [ ] `library-grid.tsx` - Griglia di poster (non rows)
- [ ] `library-header.tsx` - Filtri, sort, view toggle
- [ ] `media-poster.tsx` - Card poster Plex-style

#### 3. Detail Page (Priority: MEDIUM)

- [ ] `media-detail.tsx` - Pagina dettaglio singolo media
- [ ] `detail-hero.tsx` - Backdrop + info principale
- [ ] `detail-actions.tsx` - Play, watchlist, etc.
- [ ] `detail-metadata.tsx` - Cast, crew, info tecniche

#### 4. Player (Priority: LOW - già funzionale)

- [ ] Miglioramenti UI controlli
- [ ] Overlay info durante pausa

#### 5. Settings (Priority: LOW)

- [ ] `settings-page.tsx` - Pagina impostazioni

---

### 📂 Struttura File Proposta

```
frontend/src/
├── app/
│   ├── (main)/           # Layout con sidebar
│   │   ├── layout.tsx    # Main layout wrapper
│   │   ├── page.tsx      # Home/Dashboard
│   │   ├── movies/
│   │   │   └── page.tsx  # Movies library
│   │   ├── series/
│   │   │   └── page.tsx  # Series library
│   │   ├── media/[id]/
│   │   │   └── page.tsx  # Detail page
│   │   └── settings/
│   │       └── page.tsx
│   ├── watch/[id]/       # Player (fullscreen, no sidebar)
│   │   └── page.tsx
│   ├── login/
│   └── register/
│
├── components/
│   ├── layout/           # NEW
│   │   ├── sidebar.tsx
│   │   ├── top-bar.tsx
│   │   └── main-layout.tsx
│   │
│   ├── library/          # NEW
│   │   ├── library-grid.tsx
│   │   ├── library-header.tsx
│   │   └── media-poster.tsx
│   │
│   ├── media/            # NEW
│   │   ├── media-detail.tsx
│   │   ├── detail-hero.tsx
│   │   ├── detail-actions.tsx
│   │   └── detail-metadata.tsx
│   │
│   ├── player/           # Esistente
│   └── ui/               # shadcn (esistente)
```

---

### 🔄 Migration Plan

**Fase 1: Layout Base**

1. Creare `sidebar.tsx`
2. Creare `top-bar.tsx`
3. Creare route group `(main)` con layout
4. Testare navigazione

**Fase 2: Library Grid**

1. Creare `library-grid.tsx`
2. Creare `media-poster.tsx` (Plex-style)
3. Migrare home page a grid
4. Aggiungere filtri/sort

**Fase 3: Detail Page**

1. Creare `/media/[id]/page.tsx`
2. Componenti detail (hero, actions, metadata)
3. Link da poster a detail invece che watch

**Fase 4: Polish**

1. Animazioni/transizioni
2. Responsive mobile
3. Dark mode refinements

---

### 📸 Reference Screenshots (Analizzati)

#### 1. Sidebar

- **Larghezza**: ~200px expanded, ~60px collapsed
- **Background**: `#1a1a1a` (molto scuro)
- **Header**: Hamburger menu (☰) per collapse + Logo "tlex"
- **Collapsed state**: Solo icone, no testo
- **Menu items**:
  - Icona + testo
  - Active state: testo arancione `#e5a00d`, barra laterale arancione
  - Hover: background leggermente più chiaro
- **Sezioni**:
  - Home, Watchlist
  - TV in diretta
  - Film e Serie (con sottotitolo "Su Plex")
  - Scopri
  - ---separator---
  - Film, Serie TV, Anime (librerie)
  - Rentals
  - "Altro >" per espandere

#### 2. Top Bar

- **Search**: Input scuro con icona lente, placeholder
- **Tabs**: "Home | Di tendenza | Attività | Trova amici | Il mio profilo"
- **Right side**: icone (cast, downloads, picture-in-picture), avatar utente

#### 3. Library Grid

- **Header**: Nome libreria + breadcrumb ("Serie TV > server@...")
- **Tabs**: "Consigliati | Libreria" (tab attivo sottolineato arancione)
- **Filtri**: "Tutto ▼ | Programmi TV ▼ | Per Titolo ▼ | 10"
- **Actions**: Play, shuffle, filtri avanzati, grid toggle
- **Grid**:
  - Poster aspect ratio ~2:3
  - Gap: ~16px
  - Responsive: 6-7 colonne desktop
- **Card info sotto poster**:
  - Titolo (bold)
  - Sottotitolo: "X stagioni" o info episodio

#### 4. Media Poster Card

- **Normal state**: Solo poster
- **Hover state**:
  - Overlay scuro gradiente
  - Icona play centrata (cerchio bianco con triangolo)
  - Badge in alto a sinistra (pallino = in progress)
  - Menu "..." in alto a destra
- **Sotto poster**:
  - Titolo (bianco, medium weight)
  - Sottotitolo (grigio, small)
  - Info episodio: "S2 · E9"
- **Badge angolo destro**: Numero episodi non visti (arancione)
- **Checkmark**: Per serie completate

#### 5. Detail Page

- **Layout**: Sidebar visibile, contenuto scrollabile
- **Header**:
  - Breadcrumb: "Serie TV > server..."
  - Poster piccolo a sinistra (~150px)
  - Info a destra:
    - Titolo grande (bold)
    - Sottotitolo episodio
    - Metadata inline: "Stagione 2 · Episodio 9 | Oct 26, 2012 | 41m | TV-14"
    - Rating: "76%" con icona
    - Azioni: "Valuta e Recensisci"
- **Action buttons**:
  - "▶ Riproduci" (arancione, primary)
  - Icone: Watchlist, Check, Edit, Share, More
- **Overview**: Testo descrizione con "Altro ▼"
- **Metadata grid**:
  - Diretto da: Nome (link)
  - Scritto da: Nome (link)
  - Video: "720p (HEVC Main 10)"
  - Audio: "Italiano (OPUS Stereo) ▼"
  - Sottotitoli: "Disattivati ▼"
- **Cast e troupe**: Row orizzontale con foto circolari, nomi sotto

#### 6. Video Player

- **Layout**: Fullscreen, no sidebar
- **Top bar** (on hover):
  - Chevron down (←) per tornare indietro
  - Icone destra: PiP, fullscreen
- **Settings panel** (centro):
  - "IMPOSTAZIONI RIPRODUZIONE"
  - Qualità: "Originale (13 Mbps, 1080p HD) ▼"
  - Flusso Audio: "Italiano (EAC3 5.1) ▼"
  - Sottotitoli: "Nessuno ▼"
  - Checkbox: "Riproduci automaticamente"
- **Bottom bar**:
  - Sinistra: Titolo serie, "SX · EY — Nome episodio", tempo "2:01 / 43:07"
  - Centro: Skip back, Play/Pause, Skip next, Stop
  - Destra: More, Fullscreen, Shuffle, Playlist, Volume
- **Progress bar**: Sopra i controlli, con buffer indicator
- **Note**: SubtitlesOctopus da integrare per ASS/SSA rendering

---

## Notes

- Mantenere file < 200 righe
- Componenti piccoli e riutilizzabili
- Mobile-first responsive design
