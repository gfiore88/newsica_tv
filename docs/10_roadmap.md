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
- [/] Stream Scheduler: Script di "loop infinito" per ruotare le notizie e aggiornarle a intervalli regolari (In corso: `director.py`).
- [/] Music Integrator: Inserimento di brani musicali dell'utente nei "tempi morti" e transizioni (In corso: integrazione WAV utente).
- [ ] Gestione Errori (Watchdog): Riavvio automatico dello script FFmpeg in caso di caduta connessione o crash.
- [/] Grafica Dinamica: Ticker aggiornati in tempo reale e sovrimpressioni (Completato: Orologio e box ULTIMORA fisso).
- [ ] **Lancio Ufficiale**: Diretta pubblica sul canale NewsicaTV.
