# Account archivio — design

Data: 2026-10-26.

## Perché

Il gruppo principale e il gruppo di backup sono creati e gestiti dagli account worker,
gli stessi che fanno streaming: migliaia di richieste al giorno. Se Telegram banna quegli
account, l'utente teme di perdere tutti e due i gruppi insieme.

Serve una terza copia che non dipenda dai worker: un supergruppo di un account che TLEX
non usa mai per lo streaming, e che fa poche chiamate al giorno come un utente normale.

## Obiettivi

1. **Account archivio.** Un account Telegram con un numero dedicato, collegato da TLEX con
   lo stesso login dei worker (numero, codice, password 2FA), salvato a parte: non entra
   mai nel pool di streaming, non compare tra i worker, il suo client è acceso solo
   mentre lavora.
2. **Gruppo archivio.** Un supergruppo a topic creato e posseduto dall'account archivio,
   con gli stessi topic del gruppo principale. I messaggi li inoltra l'account archivio
   stesso: sono suoi, non di un worker. Nessun worker entra nel gruppo.
3. **Una sincronizzazione al giorno**, a blocchi di 100 inoltri, rispettando le attese di
   Telegram. Poi il client si spegne.
4. **Solo in emergenza.** Il gruppo archivio non viene mai promosso da solo e non fa da
   fallback allo streaming. Si promuove a mano dal pannello.
5. **Segue il principale.** Se il backup normale viene promosso (il principale è caduto),
   l'archivio continua dal nuovo principale senza ricopiare ciò che ha già.

## Non obiettivi

- Ricaricare i file invece di inoltrarli: un inoltro punta allo stesso file sui server di
  Telegram, quindi l'archivio protegge dai ban degli account, non dalla rimozione del file
  stesso. Con gruppi privati il rischio è basso (scelta dell'utente).
- Più di un archivio per canale.

## Come funziona

**Dati.** Tabella `archive_accounts` (numero, sessione). `backup_channels.archive_account_id`
indica un gruppo archivio. Le sessioni dell'account archivio sono un segreto come quelle
dei worker: la copia del database su Telegram le esclude.

**Entrare nel gruppo principale.** L'account archivio deve esserne membro per leggere e
inoltrare. Prima di ogni lavoro, se non lo è, un worker crea un link di invito monouso e
l'account archivio entra con quello. Copre la creazione e il dopo-promozione.

**Il client.** Si accende dalla sessione salvata, scorre i dialoghi (2–3: carica gli
`access_hash`), fa il lavoro, salva la sessione aggiornata e si spegne.

**Promozione automatica del backup normale.** I messaggi dell'archivio sono mappati sugli
id del vecchio principale. Alla promozione la mappa del backup normale (vecchio id →
nuovo id) si applica anche all'archivio: `main_channel_id`, id dei messaggi e chiavi dei
topic passano al nuovo principale. L'account archivio ci entra alla sincronizzazione
successiva.

**Promozione dell'archivio (a mano).** Prima l'account archivio fa entrare i worker attuali
nel gruppo archivio (link di invito), poi la promozione esistente sposta le parti sui
messaggi dell'archivio e crea un nuovo backup normale.

**Pannello.** Nella scheda "Aggiungi worker" una casella "Account archivio (non usato per
lo streaming)". Nella scheda backup, nel modulo di creazione, la scelta dell'account
archivio; nella lista, l'etichetta "Archivio".
