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
- [ ] **Lancio Ufficiale**: Diretta pubblica sul canale NewsicaTV.
