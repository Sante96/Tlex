# Sezione Concerti — design

Data: 2026-10-26. Terzo sottoprogetto dei concerti, dopo la barra a capitoli
(fatta) e i sottotitoli PGS (fatti).

## Perché

L'utente e un suo amico caricano su Telegram live di anime, videogiochi e altro
(il primo è "Arknights Ambience Synesthesia 2024": 73 GB, 4K HEVC, audio PCM/TrueHD,
4 tracce PGS, 34 capitoli senza nome). Oggi TLEX conosce solo film e serie: un
concerto finirebbe tra i film, abbinato a TMDB a caso, o come episodio di una serie.

L'utente guarda i concerti dal PC e salta da un brano all'altro. Li cerca per anime
o gioco ("voglio un live di Arknights"), non per artista né per data.

## Obiettivi

1. **Su Telegram, un topic per anime/gioco.** Nel gruppo si crea un topic per ogni
   anime o gioco, con il prefisso `Concerti · ` nel nome (es. `Concerti · Arknights`).
   Lo scanner riconosce il prefisso: ogni file di quel topic è un concerto di
   quell'anime/gioco, il cui nome è il nome del topic senza prefisso. Gli altri
   topic restano com'erano (film nel topic dei film, serie negli altri). I file
   divisi in parti (`.001`, `.002`, …) si raggruppano come oggi.
2. **Una scheda per anime/gioco.** Come la pagina di una serie: poster, sfondo,
   descrizione, e sotto l'elenco dei suoi concerti (immagine, titolo, data, durata,
   barra di avanzamento). Niente stagioni.
3. **La sezione.** Voce "Concerti" nella sidebar (e nella barra in basso su mobile),
   sotto Film e Serie TV: una griglia delle schede anime/gioco. In home, una riga
   "Ultimi concerti".
4. **Il concerto si guarda come un film.** Avanzamento, "Continua a guardare" (anche
   nella hero della home), watchlist e ricerca funzionano anche per i concerti.
5. **Dati da TMDB solo per la scheda anime/gioco, quando c'è.** Gli anime su TMDB
   esistono, i giochi spesso no: se TMDB trova il nome, poster, sfondo e descrizione
   arrivano da lì; altrimenti la scheda resta senza e si sistema a mano. Il singolo
   concerto non viene mai cercato su TMDB.
6. **Modifica a mano.** Dal modale "Modifica":
   - della scheda anime/gioco: nome, descrizione, poster, sfondo;
   - del concerto: titolo, data, descrizione, immagine, e la **scaletta** (i titoli
     dei brani).
7. **Brani nel player.** Nei concerti i capitoli si chiamano "Brano N" invece di
   "Capitolo N". Il nome mostrato sulla barra segue quest'ordine: titolo scritto
   nella scaletta, poi il titolo del capitolo nel file, poi "Brano N".
8. **Immagini quando TMDB non ha niente** (decise dall'utente, tutte e tre):
   - **Fotogramma dal video, automatico.** Ogni concerto ha subito un'immagine
     presa dal video stesso, senza fare niente; la scheda anime/gioco senza
     immagini TMDB usa quella del suo concerto più recente.
   - **Link incollato** nel modale "Modifica".
   - **Caricamento di un file dal PC** nel modale "Modifica".

   Un'immagine scelta a mano (link o file) vince sul fotogramma.

## Non obiettivi

- Recuperare la scaletta da internet (setlist.fm, VGMdb): si scrive o si incolla.
- Creare o spostare capitoli a mano: la scaletta dà un nome ai capitoli che il file
  ha già. Un file senza capitoli non ha scaletta.
- Pannello con l'elenco dei brani, miniature sulla barra.
- Riconoscere concerti fuori dai topic con il prefisso, o capire l'anime dal nome
  del file.
- Collegare i concerti alla pagina della serie anime omonima.
- Riproduzione automatica del concerto successivo (l'overlay "prossimo episodio").
- Lavoro specifico per la TV: la sezione ci compare come le altre, senza altro.
- Link e caricamento di immagini per film e serie: per ora solo concerti e schede
  anime/gioco (il modale è lo stesso, estenderlo dopo costa poco).
- Le immagini caricate nel backup su Telegram: stanno sul disco del server.

## Anti-obiettivi (sarebbe un fallimento anche se funziona)

- Concerti che compaiono tra i Film o tra le Serie TV.
- Un concerto abbinato da solo a un film o a un episodio di TMDB (titolo, poster e
  trama di qualcos'altro).
- Una scaletta scritta a mano che sparisce dopo "Analizza", una nuova scansione o il
  recupero dei capitoli: oggi "Analizza" riscrive `MediaItem.chapters` da ffprobe.
- Una scheda anime/gioco che si scontra con la serie dello stesso anime già in
  libreria (stesso id TMDB: `Series.tmdb_id` è unico).

## Vincoli

- Niente Alembic: tabelle nuove con `create_all_tables()`, colonne e valori nuovi
  con istruzioni idempotenti in `SCHEMA_UPGRADES` (`app/database.py`). Un valore
  nuovo di un enum PostgreSQL (`ALTER TYPE … ADD VALUE IF NOT EXISTS`) non si può
  usare nella stessa transazione in cui viene aggiunto.
- Ricostruire il backend interrompe gli stream: va chiesto all'utente prima.
- Mai due processi sulle stesse sessioni Telegram: niente backend locale, le prove
  passano dal backend Docker o da script solo-DB.
- Componenti UI dal design system (`components/ds/`), testi in `messages/it.json` e
  `en.json`.
- Oggi le immagini sono solo percorsi TMDB (`poster_path`, `backdrop_path`, messi
  dopo `image.tmdb.org` da `getTmdbImageUrl`; `next.config.ts` ammette solo quell'host)
  e il modale sceglie solo tra immagini TMDB (`ImagePickerTab`): le immagini proprie
  sono un percorso nuovo, da servire dal backend.
- Il backend in Docker monta solo `./cache` (rigenerabile). Le immagini caricate o
  scaricate da un link non si possono rigenerare: vanno su un montaggio a parte,
  persistente; i fotogrammi possono stare nella cache.
- Un link incollato è un input da non fidarsi: il backend lo scarica solo se è
  http(s), solo se la risposta è un'immagine, con un limite di dimensione (per
  esempio 10 MB) e senza seguire indirizzi interni (loopback, rete privata). Lo
  stesso controllo di tipo e dimensione vale per i file caricati.
- Il fotogramma si prende da un video 4K HEVC su Telegram: una lettura piccola vicino
  a un keyframe (c'è già `MediaItem.video_keyframes`), una volta per concerto, in
  background, uno alla volta come il recupero dei capitoli.
- I test backend girano offline (`uv run pytest`); pyright a 0 errori.

## Scelte mie (da verificare leggendo)

- **Prefisso `Concerti · `.** Riconosciuto anche con un trattino al posto del punto
  (`Concerti - Arknights`) e senza badare a maiuscole.
- **Titolo del concerto dal nome del file**, ripulito come fa lo scanner (guessit),
  tenendo l'anno se c'è; la data è l'anno se il nome lo contiene, altrimenti vuota.
- **Le modifiche ai concerti valgono per tutti**, non per utente: titolo, data,
  descrizione, immagini e scaletta sono dati della libreria condivisa. Oggi le
  modifiche a poster e sfondo di film e serie sono per utente (`UserMediaOverride`),
  e il titolo del modale non viene salvato: per i concerti va salvato davvero.
  Può modificarli qualunque utente loggato, come oggi il modale "Modifica".
- **La scaletta si scrive in un campo di testo, una riga per brano, nell'ordine**,
  così si può incollare una tracklist intera. Accanto, l'elenco dei capitoli con il
  loro orario d'inizio, per controllare che le righe tornino; righe in più o in meno
  dei capitoli vanno segnalate, non scartate in silenzio. Una riga vuota lascia il
  brano senza titolo.
- **Ricerca:** un concerto si trova per titolo e per nome dell'anime/gioco.
- **Nel player** il titolo in alto è il titolo del concerto, il sottotitolo il nome
  dell'anime/gioco.
- **Il fotogramma si prende a metà del concerto**, sul keyframe più vicino: l'inizio
  di un live è spesso nero o loghi. Ne basta uno, usato sia come immagine della card
  sia come sfondo della pagina.
- **Un link incollato viene scaricato dal backend e salvato** come un file caricato:
  così non smette di funzionare se il sito lo toglie, e il frontend non deve
  ammettere host esterni.

## Lasciato al builder

- Il modello dati: tabella nuova per le schede anime/gioco o riuso di `Series` con un
  tipo, e un nuovo `MediaType` per i concerti; purché valgano gli anti-obiettivi
  (niente concerti tra film e serie, nessuno scontro con `Series.tmdb_id`).
- Dove salvare la scaletta (colonna a parte, o altro), purché sopravviva ad
  "Analizza" e alle scansioni.
- Le API (endpoint nuovi o parametri su quelli esistenti) e le pagine frontend
  (riuso di `LibraryPage`, della pagina serie, del modale `EditMediaModal`).
- Come cercare la scheda su TMDB (ricerca TV, poi film) e cosa fare con risultati
  dubbi.
- Come rappresentare un'immagine propria in `poster_path`/`backdrop_path` (o in campi
  nuovi), il montaggio Docker per i file salvati, l'endpoint che li serve, e come il
  frontend distingue un'immagine propria da un percorso TMDB.
- Testi e icone della sezione.
