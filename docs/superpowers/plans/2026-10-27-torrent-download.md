# Download (torrent dalla seedbox a Telegram): piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Obiettivo:** dalla pagina "Download" di TLEX un utente aggiunge un magnet o un `.torrent` dicendo cos'è. La seedbox lo scarica, lo carica su Telegram nel topic giusto file per file, TLEX lo scansiona e il torrent si cancella dalla seedbox. La pagina mostra tutto in tempo reale.

**Architettura:**
- **Programma sulla seedbox** (`tools/seedbox_agent.py`): parla con qBittorrent tramite la sua API WebUI v2 e con TLEX con una sola chiamata `POST /api/v1/downloads/agent/sync` ogni 3 s. Manda lo stato e riceve i comandi.
- **Backend:** tiene i download in una tabella `downloads` e decide i topic. A fine upload lancia la scansione e poi ordina la rimozione. Gli spostamenti dopo una Modifica li fa con un client worker.
- **Frontend:** legge `GET /api/v1/downloads` ogni 3 s.

**Tecnologie:** FastAPI, SQLAlchemy async, Pyrogram 2.2.17 e guessit (backend); Python 3.10 con la sola stdlib, più Pyrogram, sulla seedbox; Next.js 16 con componenti DS e next-intl (frontend).

**Spec:** `docs/superpowers/specs/2026-10-27-torrent-download-design.md`.

## Vincoli globali

- **Accesso:** tutti gli utenti con un account (deciso da Sante). Backend con `get_current_user`; nel frontend nessun controllo su `is_admin`.
- **Categoria e tag:** in qBittorrent la categoria è esattamente `TLEX`, e ogni torrent ha il tag `tlex-<download_id>`. Il programma legge e tocca solo torrent con categoria `TLEX` **e** un tag `tlex-*`.
- **Segreti:** in TLEX non entra nessuna password della seedbox o di qBittorrent (né database, né `.env`, né log). TLEX ha solo `SEEDBOX_AGENT_TOKEN` in `.env`, di almeno 32 caratteri. Se è vuoto, gli endpoint dell'agente rispondono 404.
- **Sessione Telegram dell'agente:** si chiama `agent`, in `~/.tlex-upload/`. Mai `uploader` (quella di `telegram_upload.py`), mai la session string di un worker.
- **Topic:**
  - Film → `settings.scanner_movies_topic_id` (il topic 2, "Movie Archive");
  - Serie e Anime → `f"{name} - Stagione {season}"`;
  - Concerto → `f"Concerti · {name}"`, con il punto medio U+00B7.
- **Parti:** al massimo `4_000_000_000` byte su Premium e `2_000_000_000` altrimenti (`telegram_upload.PART_SIZE`). I nomi sono `nome.ext.001`, `.002`… e un file che sta in una parte sola mantiene il suo nome.
- **File caricabili:** quelli che `TelegramScanner().is_video_file()` accetta. Si escludono i percorsi con un pezzo che contiene `sample` e quelli dentro una cartella `Extra`, `Extras`, `Bonus`, `NCOP`, `NCED` o `NC` (senza distinguere maiuscole e minuscole).
- **Percorsi:** qBittorrent vede `/home4/sante/storage`, la shell `/storage`. La corrispondenza sta in `agent.json` → `path_map`.
- **Coda:** i torrent di TLEX vanno in cima alla coda di qBittorrent (`topPrio`), non forzati: il limite di 5 download attivi resta.
- **Tempi:** la pagina si aggiorna ogni 3000 ms e l'agente fa la sync ogni 3 s. La seedbox risulta "non collegata" dopo 30 s senza sync.
- **Grafica:** download in arancio `#e5a00d`, upload in azzurro `#38bdf8`, "in libreria" in verde `#86efac`. Componenti DS e testi in `it.json` ed `en.json`.

## Rischi da coprire con i test

1. **qBittorrent riavviato dalla piattaforma**, quindi la sessione della WebUI scade e l'API risponde 403. L'agente deve rifare il login una volta e continuare, senza perdere lo stato degli upload. → Task 5, `test_qbit_logs_in_again_after_a_restart`.
2. **Magnet senza `dn`, o `.torrent` non leggibile.** L'anteprima risponde senza nome e il modulo chiede di scriverlo. Un `.torrent` illeggibile all'aggiunta dà 400 con un messaggio. → Task 2, `test_torrent_name`; Task 3, `test_a_broken_torrent_file_is_refused`.
3. **Torrent senza video caricabili** (solo ISO o rar). Il download va in "error" con il messaggio "Nessun video da caricare", invece di restare appeso. → Task 3, `test_a_torrent_without_videos_ends_in_error`.
4. **Lo stesso magnet aggiunto due volte mentre il primo è attivo.** Risposta 409. → Task 3, `test_the_same_magnet_twice_is_refused`.
5. **Agente spento.** Dopo 30 s senza sync, `seedbox.connected` diventa false e la pagina mostra "Seedbox non collegata" con il comando per riavviarlo. → Task 3, `test_the_seedbox_shows_offline_after_30s`.

---

### Task 1: lo scanner prende la stagione dal topic

**Files:**
- Modify: `app/services/scanner/processor.py` (`process_group`, accanto al riconoscimento degli speciali)
- Test: `tests/test_topic_season.py`

**Interfaces:**
- Produces: `topic_season(topic_name: str) -> int | None` in `app/services/scanner/processor.py`.

- [ ] **Step 1: test che falliscono.** Per `process_group` si sostituiscono `tmdb_client.search_tv` (un `TMDBResult` di una serie, tmdb_id 1), `tmdb_client.get_tv_details` (None) e `tmdb_client.get_episode_details` (None), e si chiama con `client=None` e `test_session`.

```python
def test_topic_season_reads_stagione():
    assert topic_season("Stargate SG-1 - Stagione 10") == 10
    assert topic_season("Invincible - Stagione 0") == 0
    assert topic_season("Yuru Camp") is None

# process_group(test_session, group("[SubsPlease] Sousou no Frieren - 05 (1080p).mkv"), series_name="Frieren - Stagione 2")
#   -> item.season_number == 2 and item.episode_number == 5        (test_a_file_without_season_takes_the_topics)
# group("Show.S01E03.mkv"), series_name="Show - Stagione 3"
#   -> (3, 3)                                                      (test_the_topic_wins_over_the_files_season)
# group("Rakuen_Kumachi_Yuru_Camp△_OVA01_Heya_Camp_BD_1080p.mkv"), series_name="Yuru Camp - Stagione 1"
#   -> (0, 1): a special stays in season 0                         (test_a_special_stays_in_season_0)
```

- [ ] **Step 2:** `uv run pytest tests/test_topic_season.py -v` deve **fallire**: `topic_season` non esiste ancora.
- [ ] **Step 3: implementazione.** `topic_season` cerca con una regex `-\s*Stagione\s+(\d+)\s*$`, senza distinguere maiuscole e minuscole. In `process_group`, dopo il riconoscimento degli speciali: `if series_name and not is_special and (s := topic_season(series_name)) is not None: season = s`.
- [ ] **Step 4:** `uv run pytest tests/test_topic_season.py -v` → PASS. Poi `uv run pytest -q` → tutto verde.
- [ ] **Step 5:** commit `fix(scanner): a topic's "Stagione N" is its files' season`.

### Task 2: modello del download e regole dei topic

**Files:**
- Create: `app/models/download.py`, `app/services/downloads/__init__.py`, `app/services/downloads/plan.py`
- Modify: `app/models/__init__.py` (esportare `Download`)
- Test: `tests/test_download_plan.py`

**Interfaces:**
- Produces in `app/models/download.py`:
  - `class DownloadKind(StrEnum)`: `film`, `series`, `anime`, `concert`;
  - `class DownloadStatus(StrEnum)`: `queued`, `downloading`, `uploading`, `scanning`, `removing`, `library`, `error`;
  - `class Download(Base)`, tabella `downloads`. Colonne:
    - `id`, `kind: str`, `name: str | None`, `season: int | None`;
    - `magnet: Text | None`, `torrent: LargeBinary | None`, `torrent_name: str | None`, `info_hash: str | None` (indice);
    - `status: str` (default `queued`), `paused: bool` (default False), `action: str | None` (il comando in attesa: `pause`, `resume` o `remove`), `sent: bool` (default False: il comando "add" già consegnato all'agente);
    - `files: JSON` (lista di `{"path", "size", "topic", "topic_id", "progress", "message_ids", "uploaded"}`), `live: JSON | None` (l'ultimo stato del torrent dall'agente), `upload: JSON | None` (l'upload in corso);
    - `error: Text | None`, `created_at`, `updated_at`, `finished_at: DateTime | None`.

  La tabella nuova la crea già `create_all_tables()`, non serve una modifica di schema.
- Produces in `app/services/downloads/plan.py`:
  - `destination_topic(kind: DownloadKind, name: str | None, season: int | None) -> str | int`. Se manca il nome per un tipo diverso da film: `ValueError`.
  - `file_topic(kind: DownloadKind, name: str | None, season: int | None, path: str) -> str | int`. Per serie e anime usa la stagione letta da guessit dal nome del file, altrimenti `season`, altrimenti 1. Per gli speciali (`special_number(path)` diverso da None) usa la stagione 0.
  - `uploadable(path: str) -> bool`.
  - `torrent_name(magnet: str | None, torrent: bytes | None) -> str | None`: il `dn` del magnet, oppure `info.name` del `.torrent` (decodifica bencode minima, None se il file non è valido).
  - `info_hash(magnet: str) -> str | None`: lo `xt=urn:btih:` in minuscolo.
  - `guess(torrent_name: str) -> dict`: restituisce `{"name": str | None, "season": int | None}`, con il titolo e la stagione letti da guessit.

- [ ] **Step 1: test che falliscono** (con `settings.scanner_movies_topic_id` sostituito da 2):

```python
def test_destination_topics():
    assert destination_topic(DownloadKind.film, None, None) == 2
    assert destination_topic(DownloadKind.series, "Stargate SG-1", 1) == "Stargate SG-1 - Stagione 1"
    assert destination_topic(DownloadKind.anime, "Frieren", 2) == "Frieren - Stagione 2"
    assert destination_topic(DownloadKind.concert, "Love Live!", None) == "Concerti · Love Live!"

def test_a_pack_sends_each_file_to_its_season():
    t = lambda p: file_topic(DownloadKind.series, "The Expanse", 1, p)
    assert t("The.Expanse.S02E03.mkv") == "The Expanse - Stagione 2"
    assert t("Episode 05.mkv") == "The Expanse - Stagione 1"
    assert t("The_Expanse_OVA01.mkv") == "The Expanse - Stagione 0"

def test_uploadable_files():
    assert uploadable("Show/S01E01.mkv") and uploadable("Show/S01E01.MP4")
    assert not uploadable("Show/Sample/sample.mkv")
    assert not uploadable("Show/Extras/NCOP1.mkv")
    assert not uploadable("Show/cover.jpg") and not uploadable("Show/disc.iso")

def test_torrent_name():
    assert torrent_name("magnet:?xt=urn:btih:ABC&dn=Stargate.SG-1.S01.1080p", None) == "Stargate.SG-1.S01.1080p"
    assert torrent_name("magnet:?xt=urn:btih:ABC", None) is None
    assert torrent_name(None, b"d4:infod4:name9:Some.Showee") == "Some.Show"
    assert torrent_name(None, b"not bencode") is None
    assert info_hash("magnet:?xt=urn:btih:ABCdef&dn=x") == "abcdef"

def test_guess_prefill():
    assert guess("Stargate.SG-1.S01.1080p.BluRay.x264") == {"name": "Stargate SG-1", "season": 1}
```

- [ ] **Step 2:** `uv run pytest tests/test_download_plan.py -v` → FAIL (il modulo non esiste).
- [ ] **Step 3:** implementazione di modello e funzioni con le firme scritte sopra. `special_number` viene da `app.services.scanner.processor`.
- [ ] **Step 4:** `uv run pytest tests/test_download_plan.py -v` → PASS.
- [ ] **Step 5:** commit `feat(downloads): the download model and where its files go`.

### Task 3: servizio e API (pagina e agente)

**Files:**
- Create: `app/services/downloads/service.py`, `app/schemas/download.py`, `app/api/v1/downloads.py`
- Modify: `app/config.py` (`seedbox_agent_token: str = ""`), `app/api/v1/__init__.py` (montare `downloads.router`), `app/schemas/__init__.py`
- Test: `tests/test_downloads_api.py`

**Interfaces:**
- Consumes: Task 2 (modello e `plan.*`); `scanner_service.scan_all_channels(session, topic_id=...)`.
- Produces: gli endpoint qui sotto (il frontend del Task 6 e l'agente del Task 5 usano esattamente queste forme).

Endpoint della pagina (`/api/v1/downloads`, `get_current_user`):
- `GET ""` → `{"seedbox": SeedboxStatus, "downloads": [DownloadOut]}`.
  - `SeedboxStatus`: `connected`, `last_seen`, `free_bytes`, `dl_speed`, `up_speed`.
  - `DownloadOut`: `id`, `kind`, `name`, `season`, `torrent_name`, `status`, `paused`, `error`, `files`, `live`, `upload`, `topics` (i topic dei file, senza doppioni), `created_at`, `finished_at`.
- `POST "/preview"`, form con `magnet?` e `torrent?` (UploadFile) → `{"torrent_name", "name", "season"}`.
- `POST ""`, form con `magnet?`, `torrent?`, `kind`, `name?` e `season?` → 201 con `DownloadOut`.
  - 400 se mancano sia il magnet sia il `.torrent`, se il `.torrent` non è valido (`torrent_name` None), o se manca il nome per un tipo diverso da film.
  - 409 se un download non in "library" ha lo stesso `info_hash` del magnet. I `.torrent` doppi si scoprono quando l'agente riporta l'hash: il secondo va in "error" con "Già in download".
- `PATCH "/{id}"` con `{kind, name, season}`: ricalcola `topic` per ogni file. Se ci sono file già caricati in un topic diverso, chiama `move_uploaded` (Task 4).
- `POST "/{id}/pause"` e `POST "/{id}/resume"`: impostano `action`.
- `DELETE "/{id}"`: imposta `action="remove"` e `status="removing"`. Toglie da Telegram, con un client worker, solo le parti dei file caricati a metà, cioè con `message_ids` ma `uploaded` false. Quando l'agente conferma la rimozione: se lo stato era "library" il download resta come storico, altrimenti la riga si cancella.

Endpoint dell'agente (`/api/v1/downloads/agent`, header `X-Agent-Token`): token non configurato → 404, token sbagliato → 401, confronto con `hmac.compare_digest`.
- `POST "/sync"`:
  - il corpo è `AgentSync`: `free_bytes`, `dl_speed`, `up_speed`, poi `torrents` (lista di `{download_id, hash, state, progress, dlspeed, upspeed, num_peers, num_seeds, eta, size, files: [{path, size, progress}]}`), `uploads` (lista di `{download_id, path, topic_id, message_ids}`, i file finiti), `current_upload` (`{download_id, path, part, parts, percent, speed, eta}` oppure null), `removed` (lista di id) ed `errors` (lista di `{download_id, error}`);
  - la risposta è `AgentCommands`: `add` (lista di `{download_id, magnet, torrent_b64}`), `pause`, `resume` e `remove` (liste di id), e `plans` (lista di `{download_id, files: [{path, topic}]}`, con tutti i download attivi che hanno file).
- Funzioni di servizio:
  - `async def handle_sync(session, report: AgentSync) -> AgentCommands`;
  - `def seedbox_status(now: float | None = None) -> dict`, che tiene lo stato in memoria nel modulo;
  - `async def add_download(...)`.

Passaggi di stato dentro `handle_sync`:
- **Aggiunta:** `queued`, con `sent=False`. Il primo `add` consegnato porta `sent=True`.
- **Primo resoconto con i file:** si filtrano con `uploadable` e si calcolano i topic con `file_topic`. Se non resta nessun file: `error` con "Nessun video da caricare". Altrimenti `downloading`.
- **Durante l'upload:** con `current_upload` presente, `uploading`. Ogni elemento di `uploads` segna il suo file come `uploaded` e ne salva `message_ids` e `topic_id`.
- **Tutti i file caricati:** `scanning`, poi in background `scan_all_channels(session, topic_id=t)` per ogni `topic_id`. Se lo scanner è già occupato si riprova ogni 30 s, al massimo 20 volte. Poi `action="remove"` e `removing`.
- **`removed` dall'agente:** `library` e `finished_at`.

- [ ] **Step 1: test che falliscono.** Si usano il client e le intestazioni utente delle fixture esistenti. `settings.seedbox_agent_token` si imposta con monkeypatch a `"t" * 32`.
  - `test_downloads_need_a_login_not_an_admin`: GET senza login → 401; GET con un utente non admin → 200.
  - `test_adding_a_magnet_queues_it_and_the_agent_gets_it`: POST con kind series, name "Stargate SG-1", season 1 e un magnet → 201, `status == "queued"`. La sync risponde con `add[0].download_id` uguale all'id e con il magnet. Una seconda sync non ripete l'`add`.
  - `test_the_same_magnet_twice_is_refused`: lo stesso magnet una seconda volta → 409.
  - `test_a_broken_torrent_file_is_refused`: POST con `torrent=b"junk"` → 400.
  - `test_files_get_their_topics`: la sync riporta i file `["S/Stargate.SG-1.S01E01.mkv", "S/Sample/sample.mkv"]`. Nella sync dopo, `plans` contiene solo il primo, con il topic "Stargate SG-1 - Stagione 1".
  - `test_a_torrent_without_videos_ends_in_error`: file `["disc.iso"]` → `status == "error"`, errore "Nessun video da caricare".
  - `test_all_files_uploaded_scans_then_removes`: lo scanner sostituito da un `AsyncMock`, poi `uploads` per tutti i file. Lo scanner viene chiamato con `topic_id`, la sync dopo ha l'id in `remove`, e dopo `removed=[id]` lo stato è "library".
  - `test_agent_needs_its_token`: senza token configurato → 404, con un token sbagliato → 401.
  - `test_the_seedbox_shows_offline_after_30s`: `seedbox_status(now=last_seen + 31)["connected"] is False`, e `+5` dà True.
  - `test_remove_only_touches_the_seedbox`: un download in "library" con un file caricato e uno a metà (`message_ids [50]`, `uploaded` false), e il client worker sostituito. DELETE: `delete_messages` viene chiamato con `[50]` e basta, e i `MediaItem` restano.
- [ ] **Step 2:** `uv run pytest tests/test_downloads_api.py -v` → FAIL.
- [ ] **Step 3:** implementazione di servizio, schemi, router e montaggio.
- [ ] **Step 4:** `uv run pytest tests/test_downloads_api.py -v` → PASS. Poi `uv run pytest -q`, `uv run ruff check app/`, `uv run ruff format app/` e `uvx pyright app tests`: tutto verde.
- [ ] **Step 5:** commit `feat(downloads): the page's and the seedbox agent's API`.

### Task 4: spostare i file già caricati e pulire i backup

**Files:**
- Create: `app/services/downloads/move.py`
- Modify:
  - `app/models/backup.py`: `BackupMessage.pending_delete: bool`, default False;
  - `app/database.py`: aggiungere a `SCHEMA_UPGRADES` lo statement `ALTER TABLE backup_messages ADD COLUMN IF NOT EXISTS pending_delete BOOLEAN NOT NULL DEFAULT FALSE`;
  - `app/services/backup/_sync_mixin.py`: in `sync_archive`, prima di `sync_messages`, cancellare le copie con `pending_delete`.
- Test: `tests/test_download_move.py`

**Interfaces:**
- Produces: `async def move_uploaded(session: AsyncSession, download: Download, client: Client) -> None` e `async def topic_id_for(client: Client, chat_id: int, topic: str | int) -> int` (lo trova o lo crea).
- Consumes: il chat id del gruppo da `settings.channel_ids_list[0]`; il client da `worker_manager.get_best_worker(session)`, a cura di chi chiama, cioè il PATCH del Task 3.

Funzionamento: per ogni file `uploaded` il cui `topic` non corrisponde più al suo `topic_id`:
1. `client.forward_messages(chat_id, chat_id, message_ids, message_thread_id=new_topic_id, send_copy=True)` restituisce i messaggi nuovi;
2. `client.delete_messages(chat_id, old_ids)`;
3. si cancellano i `MediaItem` che hanno una `MediaPart` con `channel_id == chat_id` e `message_id` tra i vecchi id;
4. per i `BackupMessage` con `main_message_id` tra i vecchi id: se il backup è dei worker (`archive_account_id` None) si cancellano da quel gruppo con `client.delete_messages(backup_channel_id, ids)` e si eliminano le righe; se è un archivio si imposta `pending_delete=True`;
5. si aggiornano `message_ids` e `topic_id` del file e si lancia la scansione del topic nuovo, con la stessa funzione del Task 3.

- [ ] **Step 1: test che falliscono.**
  - `test_a_move_copies_deletes_and_cleans_the_library`: un client finto in cui `forward_messages` restituisce i messaggi 900 e 901. Ne risulta: `send_copy=True` e il thread nuovo nella chiamata, `delete_messages(chat, [100, 101])`, il `MediaItem` con le parti 100 e 101 eliminato, e `message_ids == [900, 901]` sul file.
  - `test_a_move_clears_the_old_backup_copies`: un `BackupMessage` di un backup dei worker (100 → 500) dà `delete_messages(-200, [500])` e la riga eliminata. Quello di un archivio (100 → 700) resta con `pending_delete=True`.
  - `test_the_archive_deletes_its_pending_copies_at_its_daily_run`: `sync_archive` con una riga in attesa. Il client dell'archivio (con `archive_client` e `sync_messages` sostituiti) chiama `delete_messages(-300, [700])` prima di `sync_messages`, e la riga sparisce.
- [ ] **Step 2:** `uv run pytest tests/test_download_move.py -v` → FAIL.
- [ ] **Step 3:** implementazione, collegata al PATCH del Task 3.
- [ ] **Step 4:** PASS, poi la suite completa, ruff e pyright.
- [ ] **Step 5:** commit `feat(downloads): a corrected download moves on Telegram, backups included`.

### Task 5: il programma sulla seedbox

**Files:**
- Create: `tools/seedbox_agent.py`, `tools/start-agent.sh`
- Modify: `tools/telegram_upload.py`: `_send(..., on_progress: Callable[[int, int], None] | None = None)` lo chiama insieme al log che c'è già.
- Test: `tests/test_seedbox_agent.py` (importa `tools/seedbox_agent.py` aggiungendo `tools/` a `sys.path`)

**Interfaces:**
- Consumes: `POST /api/v1/downloads/agent/sync` con `AgentSync` e `AgentCommands` del Task 3; `telegram_upload.FileSlice`, `_send`, `_topics`, `_client`, `PART_SIZE`, `_load` e `_save`.
- Produces:
  - **Configurazione:** `~/.tlex-upload/agent.json`, con permessi 600: `tlex_url`, `token`, `qbit_url`, `qbit_user`, `qbit_password`, `path_map: [qbit_root, shell_root]`.
  - **Stato:** `~/.tlex-upload/agent-state.json`, con chiave `f"{download_id}|{path}|{part}"` e valore il message id.
  - **`class QBit(url, user, password)`**, con `urllib.request` e un cookie jar:
    - `login()`, `torrents() -> list[dict]` (con `category=TLEX`), `files(hash) -> list[dict]`;
    - `add(download_id, magnet, torrent, savepath)`, con `category=TLEX` e `tags=tlex-<id>`;
    - `top(hash)`, `pause(hash)`, `resume(hash)`, `delete(hash)` (con `deleteFiles=true`).

    Su un 403 rifà `login()` una sola volta e ripete la chiamata. `pause` e `resume` provano prima `/torrents/stop` e `/torrents/start` (qBittorrent 5) e, su 404, `/torrents/pause` e `/torrents/resume`.
  - **`local_path(qbit_path: str, path_map: list[str]) -> str`.**
  - **`class Agent`:**
    - `async tick()`: raccoglie lo stato da qBittorrent, solo i torrent con un tag `tlex-<id>`, chiama la sync e applica i comandi. Per un `add` salva in `<qbit_root>/downloads/qbittorrent/tlex/<id>` e poi chiama `top`. Poi conserva i `plans`.
    - `async upload_ready()`: carica i file del piano che in qBittorrent sono al 100% e non sono ancora fatti, parte per parte. Salta le parti già in `agent-state.json`. Trova o crea il topic come fa `telegram_upload.upload`. Quando un file è finito lo mette nel prossimo `uploads`.
  - **Comandi:** `python3 seedbox_agent.py login|code|password|run`. `login`, `code` e `password` riusano quelli di `telegram_upload` con `telegram_upload.SESSION = "agent"`.
  - **Avvio:** `start-agent.sh` lancia `nohup python3 seedbox_agent.py run >> ~/.tlex-upload/agent.log 2>&1 &` e salva il pid in `~/.tlex-upload/agent.pid`. Se quel pid è ancora vivo non fa niente.

- [ ] **Step 1: test che falliscono.**
  - `test_qbit_paths_are_read_from_the_shell`: `local_path("/home4/sante/storage/downloads/qbittorrent/tlex/7/x.mkv", ["/home4/sante/storage", "/storage"])` restituisce `"/storage/downloads/qbittorrent/tlex/7/x.mkv"`.
  - `test_qbit_logs_in_again_after_a_restart`: un opener finto. La prima GET dà HTTPError 403, il login risponde "Ok.", la seconda GET restituisce il JSON. `torrents()` dà la lista e il login avviene una volta sola.
  - `test_only_tlex_torrents_are_reported`: tre torrent, con i tag `tlex-3`, `""` e `tlex-x`. Il resoconto contiene solo `download_id == 3`.
  - `test_an_uploaded_part_is_not_sent_again`: lo stato contiene la parte 0 di un file da due parti. Con `_send` sostituito, `upload_ready()` lo chiama solo per la parte 1.
  - `test_pause_falls_back_to_the_old_api`: `/torrents/stop` dà 404 e `/torrents/pause` 200, quindi `pause()` riesce.
- [ ] **Step 2:** `uv run pytest tests/test_seedbox_agent.py -v` → FAIL.
- [ ] **Step 3:** implementazione. Su Python 3.10 sulla seedbox si usa solo la stdlib più Pyrogram, niente librerie nuove. Un'eccezione in `tick()` finisce nel log, segue un'attesa di 10 s e il ciclo continua. L'upload gira in un task asyncio a parte, così la sync continua a riportare il suo avanzamento.
- [ ] **Step 4:** PASS, poi la suite completa.
- [ ] **Step 5:** commit `feat(downloads): the seedbox agent`.

### Task 6: frontend, API e pagina Download

**Files:**
- Create:
  - `frontend/src/lib/api/downloads.ts` (da riesportare in `lib/api/index.ts`);
  - `frontend/src/app/(main)/downloads/page.tsx`;
  - `frontend/src/components/downloads/add-torrent-card.tsx`, `torrent-card.tsx`, `seedbox-status.tsx`.
- Modify: `frontend/messages/it.json`, `frontend/messages/en.json` (sezione `downloads`).

**Interfaces** (le forme del Task 3):

```ts
export type DownloadKind = "film" | "series" | "anime" | "concert";
export type DownloadStatus = "queued" | "downloading" | "uploading" | "scanning" | "removing" | "library" | "error";
getDownloads(): Promise<{ seedbox: SeedboxStatus; downloads: Download[] }>;
previewTorrent(input: { magnet?: string; torrent?: File }): Promise<{ torrent_name: string | null; name: string | null; season: number | null }>;
addDownload(input: { magnet?: string; torrent?: File; kind: DownloadKind; name?: string; season?: number }): Promise<Download>;
updateDownload(id: number, body: { kind: DownloadKind; name: string | null; season: number | null }): Promise<Download>;
pauseDownload(id: number): Promise<void>; resumeDownload(id: number): Promise<void>; removeDownload(id: number): Promise<void>;
```

Comportamento:
- **Aggiornamento:** `getDownloads` ogni 3000 ms finché il documento è visibile.
- **Schede**, come la variante A della bozza:
  - etichetta del tipo, nome del torrent e topic;
  - barra del download (`live.progress`, arancio), con percentuale, velocità, peer e seed, ETA, e "x/y file su Telegram";
  - barra dell'upload (`upload.percent`, azzurro), con la parte n/m, la velocità e l'ETA;
  - stato "In libreria · rimosso dalla seedbox" in verde;
  - azioni: Pausa/Riprendi, Modifica (un modal DS con tipo, nome e stagione) e Rimuovi. Il testo della conferma di Rimuovi è: "Cancella il torrent e i suoi dati dalla seedbox. Quello che è già in libreria resta."
- **Riquadro di aggiunta:**
  - un campo per il magnet e una zona dove trascinare o scegliere il `.torrent`; l'anteprima precompila nome e stagione;
  - il tipo si sceglie con un selettore a segmenti; la stagione compare solo per serie e anime;
  - sotto c'è la riga "Andrà nel topic …", calcolata con le stesse regole del backend;
  - "Aggiungi" è attivo solo con un magnet o un file, più il nome per i tipi diversi da film.
- **Seedbox non collegata:** il messaggio mostra il comando `bash ~/tlex-upload/start-agent.sh`.

- [ ] **Step 1:** `cd frontend && npx tsc --noEmit && npm run lint` → verde dopo la scrittura.
- [ ] **Step 2: verifica visiva.** Sul dev server della 3001, col pattern CDP dello scratchpad (porte alte libere, `--mute-audio`, controllo che la porta sia nostra). `GET /api/v1/downloads` si sostituisce con tre download finti: uno in download, uno in upload e uno in libreria. Si fanno due screenshot, a 1600×900 e 393×852, e si confrontano con la bozza A.
- [ ] **Step 3:** commit `feat(downloads): the Download page`.

### Task 7: navigazione

**Files:**
- Modify:
  - `frontend/src/components/layout/sidebar.tsx`: voce "Download" (icona `Download` di lucide, href `/downloads`) prima di Impostazioni in `bottomRoutes`, per tutti;
  - `frontend/src/components/layout/top-bar.tsx`: voce "Download" nel menu dell'avatar, accanto a Impostazioni, con la stessa visibilità, per tutti;
  - `messages`: `nav.downloads`, cioè "Download" sia in italiano sia in inglese.

- [ ] **Step 1:** `npx tsc --noEmit && npm run lint` → verde.
- [ ] **Step 2: controllo CDP**, con `auth/me` sostituito da un utente **non admin**: la sidebar mostra "Download" subito sopra "Impostazioni", e a 393×852 il menu dell'avatar mostra "Download".
- [ ] **Step 3:** commit `feat(downloads): Download in the sidebar and the avatar menu`.

### Task 8: messa in funzione

Questo task non ha codice. Prima chiedo a Sante il via per ricostruire la VPS e le credenziali della WebUI di qBittorrent.

- [ ] **Step 1: token.** Va generato con `python -c "import secrets; print(secrets.token_urlsafe(32))"` e scritto in `/opt/tlex/.env` come `SEEDBOX_AGENT_TOKEN=...`. Poi il deploy, come da memoria: `git archive` e `docker compose up -d --build --no-deps backend frontend`.
- [ ] **Step 2: seedbox.** Si copiano `tools/seedbox_agent.py`, `tools/telegram_upload.py` e `tools/start-agent.sh` in `~/tlex-upload/` e si scrive `~/.tlex-upload/agent.json` con permessi 600.
- [ ] **Step 3: login dell'agente.** `python3 seedbox_agent.py login +39…`, poi `code <codice>`: il codice arriva nell'app Telegram di Sante. Poi `bash start-agent.sh`. In `agent.log` deve comparire la prima sync, e nella pagina "Seedbox collegata".
- [ ] **Step 4: prova completa** con un torrent pubblico e legale (Big Buck Bunny, tipo Film):
  1. scarica e la scheda mostra i dati;
  2. carica in "Movie Archive";
  3. la scansione lo mette in libreria;
  4. sparisce dalla seedbox e la scheda passa a "In libreria".

  Alla fine si chiede a Sante se tenere il titolo di prova.
