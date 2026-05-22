# Roadmap & MVP

Per ottimizzare i tempi e i token di sviluppo, bypasseremo le simulazioni locali "finte" e opereremo direttamente in ambiente di produzione (o pre-produzione) tramite stream privati su YouTube.

## MVP 1 — Core Live Stream (YouTube Privato)
**Obiettivo:** Creare il motore base e mandarlo subito in streaming su una diretta YouTube privata/non in elenco per debuggare l'output audio/video "dal vivo".
- [x] Ingestion: Script Python per prelevare 2-3 notizie da feed RSS gratuiti.
- [x] Script Generator: Configurazione LLM Locale (Ollama) per la riscrittura da "anchor-man".
- [x] Audio/Voice: Integrazione di Kokoro AI (o alternativo locale) per il TTS.
- [x] Regia & Broadcast: Comando/Script FFmpeg che unisce background loop + audio + ticker testuale e invia il flusso RTMP direttamente alla Stream Key di YouTube.
- [x] Debug: Verificare qualità voce, sincronizzazione e stabilità dello stream in formato privato.

## MVP 2 — Automazione H24 e Palinsesto (Canale Pubblico)
**Obiettivo:** Estendere la rotazione all'infinito e preparare il rilascio al pubblico.
- [x] Stream Scheduler: Script di "loop infinito" per ruotare le notizie e aggiornarle a intervalli regolari (`director.py`).
- [x] Music Integrator: Inserimento di brani musicali nei "tempi morti" (creato sistema di filler audio).
- [x] Gestione Errori (Watchdog): Loop di riavvio in `stream.sh` e creato `watchdog.sh` per `director.py`.
- [x] Grafica Dinamica: Ticker aggiornati in tempo reale e sovrimpressioni (Orologio e box ULTIMORA fisso).
- [x] Stabilizzazione Stream: Clock video costante a 30 fps, pacing realtime della pipe audio e fallback PCM coerente.
- [x] Anti-stallo H24: fallback a silenzio PCM quando la coda e' vuota e watchdog FFmpeg su `out_time_ms`.
- [x] **Protocollo Debug Live dai Log (ADR 0025)**: Ogni incidente su diretta, audio, palinsesto, overlay, RTMP o processi deve partire da `manage.sh status`, `director.log`, `stream.log`, `ffmpeg_progress.txt`, stato runtime e verifica runner prima di qualunque diagnosi o fix.
- [x] **Live Health End-to-End**: Aggiunto `./manage.sh live-health` per verificare in un solo comando processi, log, progress FFmpeg, runner locale, connessione RTMP e player pubblico YouTube.
- [x] **Invalidazione Audio Temporaneo (ADR 0026)**: Al cambio fascia il Director elimina `audio.wav`, `audio_part*.wav` e `is_multipart.txt` per impedire che uno slot riusi audio stale di podcast/news/meteo precedenti.
- [x] **Recupero Preparazioni Stale (ADR 0031)**: Le cartelle `preparing` vuote o troppo vecchie non bloccano piu' la pre-produzione; gli slot correnti possono essere rigenerati entro una finestra di recupero.
- [x] **Format Meteo Breve (ADR 0032)**: Il meteo resta un bollettino single-part da circa 3-5 minuti, seguito da rotazione musicale fino al programma successivo.
- [x] **Fix Race Condition Startup (ADR 0023)**: Risolto deadlock tra `generator_worker` e FFmpeg: introdotto `fifo_connected_event` per bloccare il precaricamento audio finché FFmpeg non si connette; ridotto `audio_queue maxsize` da 5000 a 200 chunk (~17s di buffer sicuro).
- [x] **Overlay Grafico Locale (ADR 0028)**: Spostata la HUD ON AIR/orologio/prossimi eventi da filtri FFmpeg monolitici a `overlay_agent.py`, che renderizza frame RGBA via Pillow su FIFO rawvideo locale.
- [x] **Coerenza Titolo-Contenuto (ADR 0029)**: Il titolo dello slot diventa tema obbligatorio nel prompt e gli asset pronti vengono validati tramite manifest rubrica/titolo prima della messa in onda.
- [x] Rotazione agenti robusta: fallback locale per copioni news/sport/meteo quando Ollama non e' disponibile.
- [x] Espressivita' speaker: prompt piu' parlati, punteggiatura naturale e velocita' TTS per personaggio.
- [x] Agente Wellness: rubrica fitness, benessere e cura della persona con fonti dedicate e spunti sempre vari.
- [x] Ingestion Cache & Decoupling: introdotta cache da 15 minuti su raw_news.json e disaccoppiate le responsabilità tra scraper e llm_processor.
- [x] **Diversità Fonti News (ADR 0030)**: Aggiunti feed AGI per cronaca, politica, esteri, economia, innovazione, cultura e sport; aumentata la rotazione news e aggiornati i source dei personaggi.
- [x] **Stabilizzazione Chime Orario**: introdotto arrotondamento all'ora più vicina per evitare collisioni sui confini temporali di inizio fascia palinsesto e risolti import linter.
- [x] **Segnale Orario Non Interrompente (ADR 0033)**: il chime viene schedulato una volta l'ora a minuto casuale e può andare solo come overlay sopra musica, mai sopra speaker o contenuti parlati.
- [x] **Modalità Rotazione Musica da Dashboard (ADR 0034)**: flag UI persistente per scegliere tra solo `assets/ai_music/` oppure mix `assets/music/` + `assets/ai_music/`.
- [ ] **Lancio Ufficiale**: Diretta pubblica sul canale NewsicaTV.


## MVP 3 — La "Svolta": Regia AI e Identità Editoriale
**Obiettivo:** Trasformare la playlist automatica in una vera web TV con regia autonoma, interruzioni dinamiche e format strutturati.
- [x] **Refactor Architetturale Modulare**: separare character, prompt, fonti, TTS, audio playout, overlay e runtime director in moduli dedicati mantenendo entrypoint compatibili. Fasi 1-2 avviate: character registry, prompt esterni, fallback editoriali, config TTS centralizzata e sources modulari.
- [ ] **Musica AI Locale**: generare brani brevi da 30-60 secondi con tool open-source locali, depositarli in `assets/ai_music/` e alternarli ai brani manuali senza dipendenze cloud.
- [x] **Regia AI Centrale (`DirectorAgent`)**: Refactoring del motore per gestire palinsesti veri e mantenere un file di stato in tempo reale (`runtime/on-air-state.json`).
- [x] **Breaking News Interrupt**: Agente `BreakingNewsAgent` con calcolo score urgenza, capace di interrompere il programma attuale, mandare ultim'ora con jingle speciale e riprendere.
- [ ] **Palinsesto Giornaliero Automatico**: Generazione schedulata ogni mattina (file `.md` e `.json`) per definire rubriche diverse a seconda dell'orario (mattina veloce, sera riepilogo, ecc.).
- [ ] **Identità Speaker (Personaggi AI)**: Creazione di voci AI ricorrenti per categoria (Nora: news, Leo: sport, Mia: musica, Regia: neutra) senza imitare persone reali (per policy YouTube).
- [x] **Ticker Intelligente**: Pipeline autonoma (`NewsCollector -> TickerSummarizer`) per visualizzare in basso "Ultime, Meteo, Prossimo blocco" senza limiti statici.
- [ ] **Fact-Check e Log Fonti**: Filtro anti-allucinazione interno prima del broadcast per verificare data, fonte, duplicati e veridicità.

## MVP 3.5 — Chatterbox & Podcast a Due Voci
**Obiettivo:** Introdurre rubriche speciali a due voci (podcast) interamente autogestite localmente e a costo zero tramite Chatterbox Multilingual, con fallback Kokoro.
- [x] **Spike TTS locale**: Confrontati Fish Audio S2, Kyutai Pocket TTS e Chatterbox Multilingual su copione podcast italiano.
- [x] **Provider Chatterbox Podcast**: Aggiunto modulo di sintesi locale con reference audio per Giulia e Marco.
- [x] **Reference Voci Italiane (Giulia & Marco)**: Usare `assets/voice_refs/giulia_reference.wav` e `assets/voice_refs/marco_reference.wav` come identita' vocali stabili.
- [x] **Parser Dialoghi a Turni**: Implementare in `tts_generator.py` il parsing dei tag `[SPEAKER: Nome]` per spezzare il copione in battute alternate.
- [x] **Mixer Audio Conversazionale**: Concatenare i singoli segmenti vocali introducendo micro-pause realistiche (0.3s di silenzio) per rendere naturale il dialogo.
- [x] **Fallback Kokoro**: Se Chatterbox non e' disponibile, generare il podcast con Kokoro usando voci locali Giulia/Marco.
- [x] **Aggancio Playout & Grafica**: Configurare il Director per pianificare le nuove rubriche Podcast ("Newsica Podcast", "L'Angolo del Benessere") e mostrare un overlay video personalizzato.
- [x] **Podcast Fill Serale**: Se `Newsica Sera` completa lo speaker con almeno 20 minuti residui prima delle 22:00, il Director inserisce una puntata extra `Newsica Podcast - Dopo Sera`.

## MVP 4 — Automazione Editoriale e Strumenti di Regia
**Obiettivo:** Aumentare il ritmo e l'affidabilità con controlli locali e archiviazione.
- [x] **Pre-Produzione Multi-Agente (ADR 0027)**: Introdotto Content Buffer, PreparationAgent e classi Agente (Strategist, Integrator, SysAdmin) per disaccoppiare generazione e messa in onda.
- [ ] **Riepilogo in 60 Secondi**: Bollettino orario rotante (es. "Mondo in 60 secondi", "Sport Flash") per dare la sensazione di un canale live costante.
- [ ] **Ingestion Musica Esterna a Licenza Verificata**: Studiare e integrare una API gratuita per scaricare brani in `assets/music/`, con filtro licenze, download consentito e manifest per ogni file.
- [ ] **Generatore Automatico di Format**: Agente che settimanalmente propone nuovi format documentati (durata, tono, jingle) da inserire in scaletta.
- [ ] **Dashboard Locale di Controllo**: Pannello per monitorare stato stream, uso risorse, buffer news e con pulsanti di interazione ("forza breaking", "salta").
- [ ] **Archivio Automatico Contenuti**: Salvataggio strutturato (log, script, audio) per data per mantenere traccia di tutto ciò che va in onda.

## MVP 5 — Espansione dei Formati (Crescita)
**Obiettivo:** Riciclare i contenuti H24 per massimizzare l'audience.
- [ ] **Shorts Automatici**: Estrazione e montaggio autonomo dei momenti/news salienti in file `.mp4` verticali pronti per l'upload quotidiano su Shorts.
