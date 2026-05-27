## Orchestrator Status

| 1 | /task_analyzer | Done | Brief scritto per Identità Speaker e Ticker Intelligente |
| 2 | /ai_integrator | Done | Differenziazione speaker (voci e velocità) in TTS completata |
| 3 | /python_engineer | Done | Ticker in esecuzione parallela su `director.py` e auto-aggiornante |
| 4 | /content_strategist | Done | Ampliate fonti RSS gratuite e definita rotazione anti-ripetizione |
| 5 | /python_engineer | Done | `scraper.py` ora usa memoria `tmp/recent_news.json` e bilancia le fonti |
| 6 | /python_engineer | Done | Integrati jingle classico e breaking news nella regia locale |
| 7 | /python_engineer | Done | Collegato `jingle_sport.mp3` alle rubriche sportive |
| 8 | /python_engineer | Done | Ripristino palinsesto robusto dopo Breaking News da UI |
| 9 | /streaming_expert | Sospeso | Accento colore dinamico rinviato al refactor overlay |
| 10 | /software_architect | Done | Definito piano refactor modulare per character, prompt, fonti e regia |
| 10 | /orchestrator | ✅ Done | Risoluzione architettura news, caching scraper e bug ripetizione wellness |
| 11 | /python_engineer | ✅ Done | Risoluzione collisione segnale orario e pulizia import soundfile |
| 12 | /streaming_expert | Done | Corretto overlay ON AIR sovrapposto all'orologio e disattivati accenti instabili |
| 13 | /python_engineer | Done | Refactor Fase 1: estratti character registry, prompt, fallback editoriali e config TTS |
| 14 | /python_engineer | Done | Refactor Fase 2: estratti registry fonti, RSS, rotazione, wellness e meteo da scraper |
| 15 | /python_engineer | ✅ Done | Transizione sincrona chime/breaking news per eliminazione vuoti audio |
| 16 | /python_engineer | Done | Refactor Fase 3a: estratti audio playout, music library e predisposta rotazione brani AI locali |
| 17 | /python_engineer | Done | Fix trigger UI segnale orario: comando manuale forza il chime anche vicino a cambi fascia |
| 18 | /python_engineer | Done | Segnale orario UI con `jingle_ora_esatta.mp3` e voce TTS sull'orario reale, inclusi i minuti |
| 19 | /task_analyzer | Done | Brainstorming approvato e pianificazione DirectorAgent / Trasmissione Straordinaria |
| 20 | /python_engineer | ✅ Done | Sviluppo moduli `scheduler.py`, `runtime_state.py` e `memory.py` |
| 21 | /python_engineer | ✅ Done | Sviluppo modulo `gravity_assessor.py` (valutazione urgenza news) |
| 22 | /python_engineer | ✅ Done | Sviluppo `director_agent.py` (decision engine e coda a eventi) |
| 23 | /python_engineer | ✅ Done | Refactoring di `director.py` e allineamento tag parser copioni |
| 24 | /streaming_expert | ✅ Done | Sfondo speciale per Special Broadcast ed overlay grafici |
| 25 | /code_reviewer | ✅ Done | Esecuzione test unitari e verifica di compatibilità locale a costo zero |
| 26 | /python_engineer | ✅ Done | Podcast fill serale dopo `Newsica Sera` quando resta tempo prima delle 22:00 |
| 27 | /python_engineer | ✅ Done | Rename pubblico a `Newsica Podcast` in palinsesto, prompt, dashboard e documentazione |
| 28 | /orchestrator | ✅ Done | Reso obbligatorio il protocollo "log prima delle ipotesi" per ogni debug live |
| 29 | /streaming_expert | ✅ Done | Ripristinata diretta con restart governato da `manage.sh` e aggiunto `live-health` end-to-end |
| 30 | /streaming_expert | ✅ Done | Recuperato `tmp/audio.wav` del podcast e mandato in onda con comando `PLAY_PODCAST_IMMEDIATE` |
| 31 | /python_engineer | ✅ Done | Fix audio stale: al cambio fascia il Director invalida `audio.wav`/`audio_part*.wav` e verifica TTS fresco |
| 32 | /orchestrator | ✅ Done | Refactor HUD locale: `overlay_agent.py` renderizza ON AIR/orologio/prossimi eventi su FIFO rawvideo per FFmpeg |
| 33 | /orchestrator | ✅ Done | Coerenza editoriale titolo-contenuto: tema obbligatorio nei prompt e manifest di validazione asset |
| 34 | /orchestrator | ⏳ Backlog | Studio API gratuita per ingestion musica esterna con licenze verificate e manifest locale |
| 35 | /content_strategist | ✅ Done | Espanso pool fonti news con feed AGI e rotazione più ampia per cronaca, politica, esteri, economia e cultura |
| 36 | /python_engineer | ✅ Done | Fix preparazioni stale: `preparing` vuote/vecchie non bloccano podcast e recupero slot corrente |
| 37 | /orchestrator | ✅ Done | Format meteo breve: bollettino 3-5 minuti e poi rotazione musicale fino allo slot successivo |
| 38 | /python_engineer | ✅ Done | Segnale orario random una volta l'ora, mixato solo sopra musica e mai sopra speaker |
| 39 | /python_engineer | ✅ Done | Flag dashboard per scegliere rotazione musica `solo AI` o `mix cartella music + AI` |
| 40 | /orchestrator | ✅ Done | Refactor Musica AI: worker persistente ACE-Step con coda locale, integrazione servizi e ADR 0036 |
| 41 | /orchestrator | ✅ Done | Policy prompt multilingua per Musica AI: preferenza italiano, supporto inglese e spagnolo latin con ADR 0037 |
| 42 | /orchestrator | ✅ Done | Hardening prompt Musica AI: lyrics senza placeholder e titolo sempre coerente con la lingua del brano con ADR 0038 |
| 43 | /orchestrator | ✅ Done | History persistente anti-ripetizione per la rotazione musica live con ADR 0043 |
| 44 | /orchestrator | ✅ Done | Ripristino post-migrazione DB: schema SQLite completato, compatibilità repository legacy, restart dashboard/regia e riattivazione agenti ticker/overlay/chime |
| 45 | /orchestrator | ✅ Done | Diagnostica dashboard per rotazione musica: tab dedicata con finestra recente e candidati scartati, fix selezione dry-run e allineamento ADR 0043 |
| 46 | /orchestrator | ✅ Done | Overlay `A seguire` allineato alla single source of truth runtime/DB: rimosso il coupling con `schedule_next.txt` e `current_program.txt` per la timeline live |
| 47 | /orchestrator | ✅ Done | Hardening director state machine: rimosso reset `OFFLINE` superfluo nei cambi fascia/skip e protetto il merge metadati display da sovrascritture dello stato runtime |
| 48 | /orchestrator | ✅ Done | Preparazione obbligatoria musica tematica per slot `music_only`: queue per theme, soglia minima catalogo e fallback editoriale coerente con ADR 0047 |
| 49 | /orchestrator | ✅ Done | Richieste musicali chat freeform come vincolo primario del prompt ACE-Step: parser meno distruttivo, hint lingua/dialetto e supporto LLM a `lyrics_language` non canonici con ADR 0048 |
| 50 | /orchestrator | ✅ Done | Fix live `flash_60s`: fallback non pronto ora resta in `music_rotation_until_deadline` senza silenzio; corretto anche crash `PreparationAgent` su asset slot non presenti nel palinsesto |
| 51 | /orchestrator | ✅ Done | Resa esplicita e obbligatoria la policy “test sempre” nei workflow agenti e nella documentazione operativa con ADR 0049 |
| 52 | /python_engineer | ✅ Done | Modal libreria shorts con blocchi copia/incolla per caption social e 5 hashtag pertinenti persistiti come metadati sidecar |
