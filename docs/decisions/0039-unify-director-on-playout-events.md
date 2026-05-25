# ADR 0039: Unificare il Director su `PlayoutEvent`

## Stato
Accettata - 2026-05-25

## Contesto

Il refactor del director era rimasto in uno stato ibrido:

- `DirectorAgent` restituiva ancora molti `dict` legacy con `action`.
- `director.py` manteneva un doppio path di esecuzione: uno per i `dict`, uno per i nuovi `PlayoutEvent`.
- Alcuni side effect secondari, come il trigger della generazione di nuova musica AI (`rotation_fill`), vivevano solo nel branch legacy.

Questo creava bug silenziosi:

- audio non realmente accodato pur con stato runtime aggiornato;
- podcast e special broadcast divergenti rispetto al path standard;
- trigger collaterali persi durante i refactor;
- regressioni difficili da vedere perche' non tutti i rami passavano dallo stesso contratto.

In parallelo, un job musica AI `rotation_fill` rimasto bloccato in stato `running` impediva nuove schedulazioni automatiche per giorni a causa del dedupe sui job attivi.

## Decisione

Completiamo il refactor e imponiamo un solo protocollo interno di regia:

- `DirectorAgent` deve restituire solo istanze di `PlayoutEvent`.
- `director.py` deve eseguire solo `PlayoutEvent`.
- Gli eventi di controllo, non solo quelli audio, devono essere modellati come eventi tipizzati.
- I side effect dei brani musicali, inclusa la schedulazione di nuova musica AI, devono vivere negli eventi stessi.

Inoltre:

- i job musica AI in stato `running` oltre una soglia configurabile (`AI_MUSIC_RUNNING_STALE_SECONDS`, default `3600`) vengono auto-convertiti in `failed`;
- il jingle di ingresso in `SPECIAL_BROADCAST` deve essere davvero eseguito, non solo costruito e poi ignorato dal chiamante.

## Conseguenze

Benefici:

- un solo path live da mantenere e testare;
- meno divergenze tra rubriche standard, podcast e special broadcast;
- ripristino affidabile del trigger automatico della musica AI;
- comportamento piu' prevedibile nei refactor successivi.

Costi:

- alcuni test legacy andavano riscritti per il nuovo contratto a eventi;
- `director.py` resta ancora un runtime importante, ma senza il bridge di compatibilita' piu' fragile.

## Implementazione

- `src/newsica/domain/playout_events.py`
  - introdotto `PlayoutExecutionContext`
  - introdotto `TriggerNextBlockEvent`
  - resi opzionali i `next_segment`
  - spostato il trigger `rotation_fill` dentro `PlayMusicEvent`
- `src/newsica/broadcast/director_agent.py`
  - eliminati i ritorni `dict` nei rami di regia
  - allegato `active_idx` direttamente agli eventi
- `src/director.py`
  - rimosso il branch di compatibilita' `dict`
  - aggiunto esecutore unico `execute_playout_event(...)`
  - eseguito davvero il jingle di ingresso per `SPECIAL_BROADCAST`
- `src/newsica/audio/ai_music_jobs.py`
  - auto-expire dei job `running` orfani

## Verifica

Test eseguiti:

- `python3 -m py_compile src/director.py src/newsica/broadcast/director_agent.py src/newsica/domain/playout_events.py src/newsica/broadcast/planner.py`
- `PYTHONPATH=src venv/bin/python3 -m unittest src/newsica/tests/test_director_agent.py src/newsica/tests/test_ai_music_jobs.py src/newsica/tests/test_director_breaking_state.py`

Esito:

- test unitari `OK`
- nuovo job `rotation_fill` accodato e preso in carico dal worker dopo la pulizia automatica del job orfano
