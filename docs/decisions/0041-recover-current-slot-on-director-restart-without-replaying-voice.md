# ADR 0041: Recuperare lo slot corrente al restart del Director senza replay della voce

## Stato
Accettata - 2026-05-25

## Contesto

Fino ad ora il `director` scriveva sempre `{"status": "OFFLINE"}` al boot.

Con questa scelta:

- ogni restart del solo `director.py` forzava `DirectorAgent` a reinizializzare lo slot corrente;
- podcast e rubriche multipart ripartivano dall'inizio del parlato;
- i restart tecnici generavano replay editorialmente scorretti della parte 1 o dell'intera puntata.

Allo stesso tempo, la regia non ha un modo affidabile per riprendere un file PCM esattamente a meta' battuta dopo il riavvio del processo.

## Decisione

Introduciamo una recovery di startup basata sullo stato runtime:

- se lo stato salvato appartiene ancora allo slot wallclock corrente, il director prova a recuperarlo;
- se il segmento era gia' musicale, lo mantiene;
- se il segmento era parlato e quindi non riprendibile a meta' file, il director degrada il blocco a `music_rotation_until_deadline`;
- per i podcast il recovery forza anche `podcast_played = true` per evitare che la puntata riparta dall'inizio;
- se lo slot salvato e' stale o non coerente con il wallclock, il director resta `OFFLINE` e riparte normalmente.

Per `SPECIAL_BROADCAST` il contesto viene conservato, ma un segmento in `broadcast_body` viene riportato a `broadcast_waiting` per non fingere una ripresa sample-accurate del bollettino.

## Conseguenze

Benefici:

- niente replay artificiale del parlato dopo restart tecnici;
- continuita' editoriale della fascia corrente preservata;
- comportamento piu' coerente per deploy e recovery del watchdog.

Tradeoff:

- se il restart avviene durante un contenuto parlato, si perde la prosecuzione della voce in corso;
- la recovery privilegia la continuita' di slot rispetto alla continuita' sample-accurate dell'audio.

## Implementazione

- `src/director.py`
  - aggiunta `build_restart_recovery_state(...)`
  - `main()` usa la recovery invece di forzare sempre `OFFLINE`

## Verifica

Test eseguiti:

- `python3 -m py_compile src/director.py src/newsica/tests/test_director_restart_recovery.py`
- `PYTHONPATH=src venv/bin/python3 -m unittest src/newsica/tests/test_director_restart_recovery.py`

Validazione runtime:

- restart del director durante slot podcast attivo;
- verifica che il log mostri recovery dello slot corrente;
- verifica che lo stato runtime degradi a `music_rotation_until_deadline` invece di reinizializzare il podcast da capo.
