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
- [x] Rotazione agenti robusta: fallback locale per copioni news/sport/meteo quando Ollama non e' disponibile.
- [x] Espressivita' speaker: prompt piu' parlati, punteggiatura naturale e velocita' TTS per personaggio.
- [x] Agente Wellness: rubrica fitness, benessere e cura della persona con fonti dedicate e spunti sempre vari.
- [x] Ingestion Cache & Decoupling: introdotta cache da 15 minuti su raw_news.json e disaccoppiate le responsabilità tra scraper e llm_processor.
- [x] **Stabilizzazione Chime Orario**: introdotto arrotondamento all'ora più vicina per evitare collisioni sui confini temporali di inizio fascia palinsesto e risolti import linter.
- [ ] **Lancio Ufficiale**: Diretta pubblica sul canale NewsicaTV.


## MVP 3 — La "Svolta": Regia AI e Identità Editoriale
**Obiettivo:** Trasformare la playlist automatica in una vera web TV con regia autonoma, interruzioni dinamiche e format strutturati.
- [ ] **Refactor Architetturale Modulare**: separare character, prompt, fonti, TTS, audio playout, overlay e runtime director in moduli dedicati mantenendo entrypoint compatibili. Fasi 1-2 avviate: character registry, prompt esterni, fallback editoriali, config TTS centralizzata e sources modulari.
- [ ] **Musica AI Locale**: generare brani brevi da 30-60 secondi con tool open-source locali, depositarli in `assets/ai_music/` e alternarli ai brani manuali senza dipendenze cloud.
- [ ] **Regia AI Centrale (`DirectorAgent`)**: Refactoring del motore per gestire palinsesti veri e mantenere un file di stato in tempo reale (`runtime/on-air-state.json`).
- [ ] **Breaking News Interrupt**: Agente `BreakingNewsAgent` con calcolo score urgenza, capace di interrompere il programma attuale, mandare ultim'ora con jingle speciale e riprendere.
- [ ] **Palinsesto Giornaliero Automatico**: Generazione schedulata ogni mattina (file `.md` e `.json`) per definire rubriche diverse a seconda dell'orario (mattina veloce, sera riepilogo, ecc.).
- [ ] **Identità Speaker (Personaggi AI)**: Creazione di voci AI ricorrenti per categoria (Nora: news, Leo: sport, Mia: musica, Regia: neutra) senza imitare persone reali (per policy YouTube).
- [ ] **Ticker Intelligente**: Pipeline autonoma (`NewsCollector -> TickerSummarizer`) per visualizzare in basso "Ultime, Meteo, Prossimo blocco" senza limiti statici.
- [ ] **Fact-Check e Log Fonti**: Filtro anti-allucinazione interno prima del broadcast per verificare data, fonte, duplicati e veridicità.

## MVP 3.5 — Chatterbox & Podcast a Due Voci
**Obiettivo:** Introdurre rubriche speciali a due voci (podcast) interamente autogestite localmente e a costo zero tramite Chatterbox Multilingual, con fallback Kokoro.
- [x] **Spike TTS locale**: Confrontati Fish Audio S2, Kyutai Pocket TTS e Chatterbox Multilingual su copione podcast italiano.
- [x] **Provider Chatterbox Podcast**: Aggiunto modulo di sintesi locale con reference audio per Giulia e Marco.
- [x] **Reference Voci Italiane (Giulia & Marco)**: Usare `assets/voice_refs/giulia_reference.wav` e `assets/voice_refs/marco_reference.wav` come identita' vocali stabili.
- [x] **Parser Dialoghi a Turni**: Implementare in `tts_generator.py` il parsing dei tag `[SPEAKER: Nome]` per spezzare il copione in battute alternate.
- [x] **Mixer Audio Conversazionale**: Concatenare i singoli segmenti vocali introducendo micro-pause realistiche (0.3s di silenzio) per rendere naturale il dialogo.
- [x] **Fallback Kokoro**: Se Chatterbox non e' disponibile, generare il podcast con Kokoro usando voci locali Giulia/Marco.
- [ ] **Aggancio Playout & Grafica**: Configurare il Director per pianificare le nuove rubriche Podcast ("Newsica Talk", "L'Angolo del Benessere") e mostrare un overlay video personalizzato.

## MVP 4 — Automazione Editoriale e Strumenti di Regia
**Obiettivo:** Aumentare il ritmo e l'affidabilità con controlli locali e archiviazione.
- [ ] **Riepilogo in 60 Secondi**: Bollettino orario rotante (es. "Mondo in 60 secondi", "Sport Flash") per dare la sensazione di un canale live costante.
- [ ] **Generatore Automatico di Format**: Agente che settimanalmente propone nuovi format documentati (durata, tono, jingle) da inserire in scaletta.
- [ ] **Dashboard Locale di Controllo**: Pannello per monitorare stato stream, uso risorse, buffer news e con pulsanti di interazione ("forza breaking", "salta").
- [ ] **Archivio Automatico Contenuti**: Salvataggio strutturato (log, script, audio) per data per mantenere traccia di tutto ciò che va in onda.

## MVP 5 — Espansione dei Formati (Crescita)
**Obiettivo:** Riciclare i contenuti H24 per massimizzare l'audience.
- [ ] **Shorts Automatici**: Estrazione e montaggio autonomo dei momenti/news salienti in file `.mp4` verticali pronti per l'upload quotidiano su Shorts.
