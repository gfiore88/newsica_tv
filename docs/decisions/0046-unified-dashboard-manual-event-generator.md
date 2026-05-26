# ADR 0046: Generatore unificato eventi manuali in dashboard

Data: 2026-05-26

## Contesto

La dashboard esponeva due strumenti separati per test manuali on-demand:

- `TG News al Volo (Chiara)`
- `Newsica Podcast al Volo`

Questo creava tre problemi pratici:

- il nuovo prompt `flash_60s` non era provabile dalla UI senza patch ad hoc o trigger indiretti;
- ogni nuovo format richiedeva una card dedicata e logica duplicata lato backend;
- il playout immediato continuava a distinguere solo tra `news` e `podcast`, perdendo identita' editoriale per format come `flash_60s`, `sport`, `meteo` o `wellness`.

## Decisione

La dashboard adotta un solo pannello `Genera Evento al Volo` basato su dropdown dei format editoriali supportati.

La soluzione introduce:

- endpoint `GET /api/manual-event-formats` per esporre i format testabili;
- endpoint `POST /api/manual-event` per generare script, TTS e playout immediato;
- comando di regia generico `PLAY_EVENT_IMMEDIATE|file|title|character_id`;
- aggiornamento del director per scrivere `current_block` coerente con il format realmente mandato in onda.

Il backend riusa la pipeline locale esistente (`ContentStrategistAgent`, `AIIntegratorAgent`, `characters.json`) invece di mantenere prompt hardcoded duplicati in dashboard.

## Conseguenze

- Pro: `flash_60s` e gli altri format parlati diventano testabili dalla dashboard senza nuove card dedicate.
- Pro: la UI manuale scala con i prompt registrati e riduce duplicazione tra News, Podcast e futuri format.
- Pro: ticker, overlay e stato runtime vedono il tipo editoriale corretto durante il playout immediato.
- Contro: `music_only` resta fuori dal pannello perche' non e' un evento parlato autosufficiente.
- Contro: `podcast` mantiene logica manuale specifica sul brief, per preservare il comportamento editoriale a due speaker richiesto dalla UI on-demand.
