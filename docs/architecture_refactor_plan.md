# Piano refactor architetturale NewsicaTV

## Diagnosi attuale

La codebase funziona, ma molte responsabilita' sono concentrate in pochi file:

- `src/director.py`: regia live, schedule, queue audio, processi FFmpeg, jingle, overlay, breaking news, chime, musica, stato UI e controllo FIFO.
- `src/llm_processor.py`: prompt dei character, scelta fonti, fallback script e chiamata Ollama.
- `src/scraper.py`: definizione fonti, fetching RSS, rotazione anti-duplicati, scoring wellness, meteo e cache.
- `src/tts_generator.py`: configurazione voci, normalizzazione testo e generazione audio.

Questo rende difficile aggiungere nuovi character, nuove rubriche, nuovi formati e nuove fonti senza toccare codice runtime sensibile.

## Principio target

Separare configurazione editoriale, servizi applicativi e runtime live.

La regia deve decidere "cosa va in onda adesso" e coordinare i servizi. Non deve sapere come e' scritto un prompt, quali RSS alimentano una rubrica, quale voce usa un character, o come si costruisce un filtro editoriale.

## Struttura proposta

```text
src/
  newsica/
    config/
      paths.py
      settings.py
    domain/
      characters.py
      schedule.py
      content.py
      playout.py
      state.py
    sources/
      registry.py
      rss.py
      weather.py
      rotation.py
    editorial/
      prompts/
        news.md
        sport.md
        meteo.md
        wellness.md
        breaking_news.md
      script_generator.py
      fallback_scripts.py
      source_filters.py
    audio/
      tts.py
      mixer.py
      music_library.py
      jingles.py
      queue.py
    broadcast/
      overlay.py
      stream_state.py
      control_bus.py
    apps/
      director.py
      scraper.py
      llm_processor.py
      tts_generator.py
      dashboard.py
```

Gli script in `src/*.py` possono restare come entrypoint compatibili, ma dovrebbero delegare a `src/newsica/...`.

## Character come configurazione

Ogni character dovrebbe essere definito da dati, non da `if/elif` sparsi:

```json
{
  "id": "sport",
  "display_name": "Leo",
  "rubric_type": "sport",
  "voice": "im_nicola",
  "speed": 1.05,
  "prompt": "editorial/prompts/sport.md",
  "sources": ["ansa_sport"],
  "jingle": "assets/jingles/jingle_sport.mp3",
  "accent": "0x22c55e",
  "format": "multipart_radio_show"
}
```

Questo permette di aggiungere una nuova rubrica creando una configurazione e un prompt, senza modificare `director.py`, `llm_processor.py`, `tts_generator.py` e `stream.sh` insieme.

## Pipeline target

1. `ContentCollector`: scarica e normalizza fonti.
2. `ContentSelector`: sceglie notizie per rubrica usando memoria e filtri.
3. `ScriptGenerator`: applica prompt e fallback del character.
4. `TtsService`: produce audio singolo o multi-part.
5. `PlayoutPlanner`: decide sequenza jingle, speaker, musica e interruzioni.
6. `AudioQueue`: invia PCM alla FIFO.
7. `OverlayState`: aggiorna titolo, prossimo blocco, colore e ticker.
8. `DirectorRuntime`: coordina loop, confini orari, breaking news e comandi UI.

## Migrazione consigliata

### Fase 1 - Estrarre configurazione editoriale

- Creare `characters.json` o `characters.yaml`.
- Spostare prompt in file markdown separati.
- Far leggere a `llm_processor.py` prompt, fonti e fallback da un registry.
- Far leggere a `tts_generator.py` voce e velocita' dallo stesso registry.

Rischio basso: non cambia il flusso live, cambia solo dove stanno i dati.

### Fase 2 - Separare sources e selezione contenuti

- Spostare `RSS_FEEDS`, gruppi fonte e scoring in `sources/`.
- Rendere `scraper.py` un entrypoint sottile.
- Produrre output piu' strutturati, ad esempio `tmp/content/news.json`, `tmp/content/sport.json`, `tmp/content/wellness.json`.

Rischio medio: va verificato che ogni rubrica riceva ancora abbastanza contenuti.

### Fase 3 - Isolare audio e playout

- [x] Estrarre music library, jingle selection, mix sidechain e queue PCM.
- [x] Introdurre oggetti evento come `PlayJingle`, `PlayVoicePart`, `PlayMusicTrack`, `UpdateOverlay`.
- [x] Far generare al planner una lista di eventi invece di avere il flusso scritto direttamente nel loop.

Rischio medio-alto: e' la parte piu' delicata per continuita' audio.

### Fase 4 - Ridurre `director.py`

- [x] Lasciare nel director solo loop runtime, comandi UI, interruzioni e gestione stato.
- [x] Spostare schedule, overlay, control file e process supervision in moduli dedicati.
- [x] Eliminare il doppio protocollo `dict`/eventi: il `DirectorAgent` emette ora solo `PlayoutEvent` tipizzati e il loop live esegue un solo path.
- [x] Portare i side effect collaterali dei brani musicali (es. trigger `rotation_fill` per la musica AI) dentro gli eventi, evitando che si perdano nei bridge legacy.
- [ ] Aggiungere test unitari su planner e selector senza avviare FFmpeg.

Rischio medio: da fare quando le fasi precedenti sono stabili.

### Fase 5 - Consolidare Memoria e Storico su SQLite (Storage Layer)

- [x] Sostituire la selva di file JSON (`ai_music_jobs.json`, `telegram_voices.json`, `editorial-memory.json`, ecc.) con un DB transazionale.
- [x] Sviluppare `src/newsica/storage/database.py` e relativi Repository.
- [x] Mantenere invariato il runtime Realtime (che continua a usare code FIFO fisiche) ma spostare su DB tutto il layer di decisione, asset lifecycle e storico.
- [x] Eseguire migrazioni trasparenti (i vecchi moduli wrapper continuano a funzionare esponendo la stessa firma ma puntando ai Repository SQLite).

Rischio basso-medio: tocca molti agenti periferici ma stabilizza enormemente i conflitti I/O.

### Fase 6 - Confine di generazione locale/remota

Obiettivo: permettere sia il funzionamento full local sia un deployment ibrido VPS+Mac senza creare due pipeline da mantenere in parallelo.

- [x] Introdurre `NEWSICA_GENERATION_MODE=local|remote`, con default `local`.
- [x] Estrarre un contratto applicativo unico per la generazione contenuti (`GenerationClient` o equivalente).
- [x] Far dipendere `preparation_agent.py` dal contratto, non direttamente dai dettagli di `AIIntegratorAgent`, TTS o worker musica AI.
- [x] Implementare `LocalGenerationClient` come adapter del comportamento attuale.
- [x] Progettare `RemoteGenerationClient` come adapter verso una coda job gestita dal VPS.
- [ ] Leggere URL, token, worker id, host SSH, path remoti, polling e heartbeat solo da environment/config privata; niente valori personali o credenziali hardcoded nel codice.
- [x] Aggiungere repository `generation_jobs` con claim atomico, heartbeat, recovery stale e stati `pending/claimed/running/uploading/ready/failed/expired`.
- [x] Aggiungere worker co-located di sviluppo (`src/generation_worker.py`) avviabile in modalita' `remote`.
- [x] Validare sempre gli asset remoti in staging prima del move atomico in `runtime/assets/ready`.
- [x] Implementare trasporto HTTP Mac-VPS per claim, heartbeat e complete/fail sopra lo stesso contratto job.
- [x] Implementare upload asset Mac-VPS via HTTP multipart e pubblicazione atomica lato VPS.
- [ ] Valutare trasporto alternativo rsync/SFTP per artifact molto grandi o reti instabili.
- [ ] Mantenere la regia indipendente dal Mac: il Director legge solo asset `ready` e usa fallback se un job non rispetta la deadline.

Rischio medio: non deve cambiare la continuita' live. La prima implementazione deve essere documentale/strutturale e protetta da feature flag, poi testata su `ai_music` prima dei blocchi parlati.

## Quando usare agenti specializzati

Ha senso coinvolgerli dopo la Fase 1, quando il lavoro e' divisibile in ownership precise:

- Python engineer: estrazione moduli e compatibilita' entrypoint.
- Content strategist: struttura character, prompt e fonti.
- Streaming/audio engineer: playout planner, sidechain, FIFO e FFmpeg.
- QA/code reviewer: test di regressione su schedule, breaking news e comandi UI.

Non ha senso usarli prima di avere questa mappa, perche' rischierebbero di lavorare tutti sugli stessi file.

## Criteri di successo

- Aggiungere una rubrica nuova non richiede modifiche al loop della regia.
- Prompt e voce di un character si cambiano senza toccare codice runtime.
- Le fonti di una rubrica sono dichiarate in un registry, non in funzioni sparse.
- `director.py` scende sotto 250 righe ed e' leggibile come orchestratore.
- Il director non contiene piu' branch di compatibilita' per action legacy.
- Esistono test locali su selezione notizie, schedule, playout planner e overlay state.
