# Download: torrent dalla seedbox a Telegram, da TLEX

Data: 2026-10-27. Stato: da approvare.

## Perché

Oggi, per aggiungere qualcosa alla libreria, Sante scarica con il qBittorrent della seedbox e poi carica su Telegram, con un piano scritto a mano (`tools/telegram_upload.py`, eseguito sulla seedbox). Vuole fare tutto da TLEX: incolla un magnet o un `.torrent`, dice cos'è, e il resto succede da solo. Il titolo compare in libreria, la seedbox resta pulita, e lui vede in ogni momento cosa sta succedendo. Il riferimento è un "qBittorrent fatto nello stile di TLEX".

Scarica la **seedbox**, non la VPS (scelta di Sante dopo il confronto):
- i torrent sulla VPS Contabo porterebbero segnalazioni di copyright e il rischio di sospensione, e sulla VPS girano TLEX e altri servizi;
- la VPS ha 348 GB liberi, la seedbox 7 TB;
- la seedbox ha già qBittorrent e il caricamento verso Telegram.

## Obiettivi

1. **Pagina "Download"**, solo per l'admin, nello stile di TLEX (componenti DS, colori dell'app).
   - Desktop, TV e iPad: voce nella sidebar, **sopra Impostazioni**.
   - Telefono: la barra in basso non ha Impostazioni, che stanno nel menu dell'avatar, quindi "Download" va lì accanto (*mia scelta*).
2. **Aggiunta.** Un riquadro in cima alla pagina:
   - incolli un magnet, oppure trascini o scegli un file `.torrent`;
   - scegli il tipo: **Film, Serie, Anime, Concerto**;
   - per Serie, Anime e Concerto scrivi il **nome**; per Serie e Anime anche la **stagione**. Nome e stagione arrivano già proposti dal nome del torrent (guessit, come lo scanner) e si possono correggere;
   - sotto compare il topic di destinazione;
   - il tipo lo sceglie sempre Sante, TLEX non indovina.
3. **Topic di destinazione**, gli stessi schemi già in uso nel gruppo:
   - Film → topic 2 "Movie Archive";
   - Serie → "`<Titolo> - Stagione N`", con 0 per gli speciali;
   - Anime → come le serie, "`<Nome> - Stagione N`" (*mia scelta*). Nel gruppo gli anime già presenti sono così ("Yuru Camp - Stagione 1", "Vivy: Fluorite Eye's Song - Stagione 1"), anche quando hanno una stagione sola;
   - Concerto → "`Concerti · <Nome>`".

   Se il topic non esiste viene creato, come fa già `telegram_upload.py`.

   **Pacchetti con più stagioni** (batch di anime, "serie completa"), *mia scelta*: ogni file va nel topic della **sua** stagione, letta dal nome del file. La stagione scritta nel modulo vale per i file che non ne hanno una. La scheda mostra tutti i topic di destinazione.

   **La stagione in libreria segue il topic** (*mia scelta*, richiede di cambiare lo scanner). Oggi lo scanner prende la stagione solo dal nome del file e, se manca, mette 1: un anime "[Gruppo] Nome - 05" della seconda stagione finirebbe sopra la prima, e una Modifica della stagione non cambierebbe niente in libreria. D'ora in poi, se il nome del topic ha "Stagione N", quella è la stagione dei suoi file, anche quando il nome del file ne indica un'altra: la stagione l'ha scelta Sante. Vale solo per le scansioni nuove, perché lo scanner non rielabora i titoli già in libreria.
4. **Lista a schede**: la variante A della bozza, scelta da Sante. Ogni torrent è una scheda con:
   - tipo (etichetta colorata), nome del torrent, topic di destinazione, numero di file e dimensione;
   - **due barre**: download in arancio (`#e5a00d`) e caricamento su Telegram in azzurro;
   - dati del download: percentuale, velocità, peer (di cui seed), tempo rimanente;
   - dati del caricamento: percentuale, parte n/m, velocità, tempo rimanente, e "x/y file già su Telegram";
   - uno stato: In coda · In download · Su Telegram · In libreria · Errore (con il messaggio);
   - azioni: **Pausa/Riprendi**, **Modifica** (tipo, nome, stagione), **Rimuovi**.

   **Rimuovi** (deciso da Sante) cancella il torrent e i suoi dati **dalla seedbox**, e basta. Quello che è già su Telegram e in libreria resta. È la stessa pulizia che avviene da sola quando l'upload finisce. Se lo premi a upload in corso, si ferma, e le parti di un file rimasto a metà (un `.001` senza il resto) si tolgono da Telegram, perché nessuno potrebbe leggerle (*mia scelta*).

   In cima alla pagina c'è una riga con lo stato della seedbox: collegata o no, spazio libero, velocità totali.
5. **Caricamento file per file.** Un file finito di scaricare parte subito per Telegram, senza aspettare tutto il torrent (proposta accettata).
   - I file sopra il limite dell'account (4 GB su Premium) si spezzano in parti `.001`, `.002`… come fa già `telegram_upload.py`: lo scanner le riunisce.
6. **A lavoro finito:**
   - TLEX scansiona i topic coinvolti e i titoli compaiono in libreria;
   - poi il torrent e i suoi file **vengono cancellati dalla seedbox**;
   - la scheda resta nella lista come "In libreria · rimosso dalla seedbox".
7. **Modifica in ogni momento.**
   - Prima del caricamento cambia solo la destinazione.
   - Dopo, i file già su Telegram si **spostano**: si copiano nel topic giusto (copia del messaggio, istantanea, senza ricaricare) e si cancellano gli originali. TLEX toglie i titoli vecchi e la scansione crea quelli nuovi al posto giusto.
   - Questo l'ha approvato Sante.
   - **Anche i backup si puliscono** (*mia scelta*). Il backup orario copia i file spostati nel nuovo topic del gruppo di backup, ma le vecchie copie resterebbero nel vecchio topic: se un giorno il backup diventasse il gruppo principale, la scansione riporterebbe in libreria i titoli sbagliati. Quindi:
     - nel gruppo di backup dei worker le vecchie copie si cancellano subito, grazie alla corrispondenza già salvata (`BackupMessage`);
     - nel gruppo d'archivio le cancella l'account d'archivio al suo giro giornaliero, da un elenco che TLEX gli prepara.
8. **Solo i torrent di TLEX.** qBittorrent sulla seedbox ha molti altri download (anche tracker privati). TLEX usa una categoria tutta sua, **"TLEX"**: la pagina mostra solo quella, e niente tocca gli altri torrent.

## Fuori dal progetto

- Tracker privati: Sante li aggiunge direttamente in qBittorrent, non da TLEX.
- Seed dopo il caricamento: i torrent di TLEX si cancellano appena caricati.
- Gestire gli altri torrent della seedbox, e cercare torrent o feed RSS.
- Scaricare sulla VPS.
- Più utenti: è una pagina solo per l'admin.

## Da evitare in ogni caso

- Toccare, mettere in pausa o cancellare un torrent che non sia della categoria "TLEX".
- Tenere in TLEX (database, `.env`, log) la password della seedbox o quella della WebUI di qBittorrent.
- Usare la sessione di un worker fuori dal backend: la stessa sessione in due processi provoca AUTH_KEY_DUPLICATED e uccide la sessione.
- Ricaricare due volte lo stesso file, o la stessa parte, dopo un riavvio.

## Come è fatta la seedbox (verificato il 2026-10-27)

- La piattaforma (hulk.mygiga.cloud) tiene ogni app in un contenitore suo. Condividono lo spazio dei file, ma ognuno lo vede in un punto diverso:
  - shell SSH (Ubuntu 22.04, Python 3.10, Pyrogram 2.2.17, utente `sante` senza cron né systemd utente): `/storage/...`;
  - qBittorrent: `/home4/sante/storage/...`.

  Chi legge i percorsi di qBittorrent dalla shell deve sostituire `/home4/sante/storage` con `/storage`.
- La **WebUI di qBittorrent** risponde su `https://qbittorrent-sante.hulk.mygiga.cloud`, con l'API v2 (`/api/v2/...`). Senza login risponde 403: il login è obbligatorio, senza eccezioni per indirizzo.
- qBittorrent scarica **al massimo 5 torrent alla volta** (coda attiva) e Sante ne ha molti in coda. I torrent di TLEX vanno aggiunti **in cima alla coda** (*mia scelta*): rispettano il limite, ma passano davanti agli altri.
- La piattaforma **riavvia qBittorrent spesso**, ogni poche ore, per l'uso dello swap. La shell SSH resta su per giorni (l'uploader ha girato 19 ore di fila). Il carico della macchina è alto (load ~77).
- Dalla shell, `https://play.tlexmediaserver.space` risponde in circa 0,4 s.
- La sessione Telegram dell'uploader sta in `~/.tlex-upload/` (permessi 700), con la sua configurazione: api id/hash e id del gruppo. È un login proprio dell'account Premium (lo stesso account del worker 12, ma con un'altra sessione), quindi può girare sulla seedbox mentre il backend usa le sue.
- Da sistemare a parte, non fa parte del progetto: la categoria "Serie TV" di qBittorrent ha come percorso un URL (`https://filebrowser-sante.../serietv/`). Per questo un download è finito in una cartella che si chiama `https:`.

## Come lo costruirei (scelte mie, il costruttore può cambiarle se trova di meglio)

**Un programma sulla seedbox** (`tools/seedbox_agent.py`, in repo, copiato in `~/tlex-upload/`), sempre acceso e avviato con `nohup` come l'uploader. Fa da tramite tra TLEX e qBittorrent:
- **Solo in uscita:** parla con TLEX via HTTPS, e TLEX non deve raggiungere la seedbox. Ogni pochi secondi chiede a TLEX i comandi nuovi (aggiungi, pausa, riprendi, rimuovi, nuova destinazione) e gli manda stato e battito.
- **Credenziali:** quelle della WebUI e un token per parlare con TLEX stanno in `~/.tlex-upload/` sulla seedbox. Il token lo genera TLEX e serve solo per questi endpoint.
- **qBittorrent:** ci parla con l'API v2. Aggiunge i torrent con categoria "TLEX", ciascuno in una cartella sua sotto `downloads/qbittorrent/tlex/`, e legge avanzamento, peer e file.
- **Caricamento:** carica i file finiti riusando la logica di `telegram_upload.py` (parti, tentativi, attese) e tiene uno stato locale delle parti già caricate, così dopo un riavvio non ricarica niente.
- **Riavvii di qBittorrent:** li sopporta. Se l'API non risponde riprova e riprende da dov'era.

**Nel backend di TLEX:**
- una tabella per i torrent, con tipo, nome, stagione, topic, hash qBittorrent, stato, ultimo stato ricevuto ed errore;
- gli endpoint admin della pagina, più quelli del programma della seedbox (protetti dal token);
- a lavoro finito, la scansione dei topic coinvolti con lo scanner esistente;
- per una Modifica dopo il caricamento, la copia e la cancellazione dei messaggi, fatte con un client worker del backend, che è admin del gruppo.

**Pagina:** `app/(main)/downloads/`. Aggiorna i dati ogni 2–3 secondi mentre è aperta. Se il programma della seedbox non manda il battito da un po', mostra "Seedbox non collegata", con il comando per riavviarlo.

**File da caricare:** solo i video, con le estensioni che lo scanner riconosce. Si saltano i file di prova (`sample`) e le cartelle di extra (Extras, Bonus, NCOP/NCED) (*mia scelta*).

## Lasciato al costruttore

Il formato esatto delle API e dello stato, gli intervalli di aggiornamento, quanto a lungo restano visibili le schede finite, i tempi dei tentativi, il testo esatto dei messaggi, e come si avvia e si riavvia il programma sulla seedbox.
