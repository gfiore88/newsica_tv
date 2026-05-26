# 44. Completa Migrazione Memoria Operativa su SQLite

Date: 2026-05-26

## Status

Accepted

## Context

L'architettura di NewsicaTV è storicamente cresciuta appoggiandosi a innumerevoli file JSON salvati nella directory `runtime/` per mantenere la memoria e lo stato. Tra questi: `ai_music_jobs.json`, `telegram_voices.json`, `editorial-memory.json`, oltre agli stati asincroni come lo stato di preparazione degli asset audio generati (`preparing`, `ready`). 
Con l'aumentare dei processi attivi contemporaneamente (Watchdog, Dashboard, FFmpeg Streamer, Agent Director, Preparation Agent, System Admin Agent), i file JSON ponevano grossi problemi di conflitti e race-conditions I/O. Ad esempio, l'auto-pulizia dei job orfani o la moderazione su Telegram necessitavano continui lock/retry. 
L'utente ha richiesto di spostare lo strato di **memoria persistente, storico operativo, log decisioni e dashboard** (esclusa la FIFO per lo streaming Realtime) interamente su un DB SQLite leggero. 

## Decision

Abbiamo implementato una pipeline migratoria "trasparente" verso SQLite (`runtime/newsica.db`), suddividendola in 7 fasi, portate a compimento in questo blocco di lavoro:

1. **Asset Status (`asset_slots` e `SystemAdminAgent`)**: Il ciclo di vita dell'asset pre-calcolato è mappato su DB. Uno slot passa dallo stato `preparing`, a `ready`, fino a `played` (quando `DirectorAgent` e FFmpeg lo eseguono) o `failed`. Questo garantisce alla UI e agli script di recupero una visione univoca ed esatta del workflow.
2. **Moderazione Telegram (`telegram_requests`)**: I vocali inviati dal bot Telegram vengono scritti sulla tabella `telegram_requests`. `telegram_voices.py` è stato rifattorizzato per esporre la vecchia firma (es. `list_voices`, `approve_voice`) mascherando le chiamate SQL. In questo modo la Dashboard e il TelegramAgent non hanno subito alcuna mutazione.
3. **Task & AI Jobs (`ai_music_jobs`)**: I task generati in background (rotazioni AI Music, fallback) non usano più `ai_music_jobs.json`. Il file `ai_music_jobs.py` poggia ora su repository, con una query robusta per identificare ed espirare automaticamente job "orfani".
4. **Memoria Editoriale (`editorial_memory`)**: Sostituita la limitazione degli array a 10-30 elementi di `editorial-memory.json`. Ora, rubriche, titoli, musica e intro recenti vengono inseriti in una tabella log a inserimento continuo, interrogata per `LIMIT X` decrescente, riducendo drasticamente il payload di memoria ram.

## Consequences

- **Positivo**: Nessuna sovrascrittura accidentale del file di stato in caso di crash multipli concorrenti (SystemAdmin e Director possono scrivere/leggere contemporaneamente al database).
- **Positivo**: Le API della Dashboard ora godono di performance migliori ed è possibile effettuare query strutturate.
- **Positivo**: Il refactoring non ha intaccato lo strato di `playout` in Realtime, mantenendo invariata la purezza e velocità del flusso FIFO.
- **Negativo**: Introdurre SQLite richiede che chi ispeziona a mano lo stato debba usare il comando `sqlite3 runtime/newsica.db`, non più limitandosi a fare `cat runtime/telegram_voices.json`.
- **Note**: Si consiglia di eliminare fisicamente dal filesystem i file JSON orfani per pulizia architetturale.
