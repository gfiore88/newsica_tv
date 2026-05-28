# 📺 NewsicaTV

**NewsicaTV** è un sistema di broadcasting automatico sperimentale. L'obiettivo del progetto è generare e streammare un canale televisivo/radiofonico su YouTube Live H24, gestito interamente da Agenti AI e tool **100% locali**.

Il progetto segue due vincoli fondamentali:
1. **Zero Costi**: Nessun utilizzo di API a pagamento o servizi Cloud (es. OpenAI, ElevenLabs).
2. **Local-First**: Tutti i processi (scraping, LLM per rielaborazione testi, TTS, mix audio e regia video) devono girare localmente sulla macchina host.

## ✅ Disciplina Test

Per NewsicaTV i test non sono opzionali.

Ogni modifica a codice o runtime deve includere:
- `py_compile` sui file toccati;
- test automatici pertinenti al ramo modificato;
- verifica post-restart dei log live se la modifica tocca regia, dashboard, stream o processi residenti.

Una patch senza test automatici è da considerare incompleta anche se sembra funzionare a occhio.

## 🛠 Stack Tecnologico (Previsto)
- **Logica Core**: Python & Bash Scripts
- **Text Generation (LLM)**: Ollama (es. Llama-3) in locale per riscrivere e sintetizzare i feed RSS
- **Voice Generation (TTS)**: Modelli Voice AI open-weights locali (es. Kokoro AI)
- **Video & Regia**: FFmpeg per compositing e streaming RTMP dinamico
- **Music Generation**: Modelli AI musicali leggeri in locale (per i tempi morti)

## 📂 Struttura Documentazione
Il progetto è pesantemente documentato nella cartella `docs/`. Leggi questi file per comprendere l'architettura:
- `docs/00_overview.md`: Visione del progetto e vincoli
- `docs/03_architecture.md`: Diagramma dell'architettura e disaccoppiamento moduli
- `docs/10_roadmap.md`: MVP e tabella di marcia
- `docs/decisions/`: Repository degli ADR (Architecture Decision Records)

## 🤖 Il Team (Multi-Agente)
Lo sviluppo è supportato da un team di agenti AI specializzati con direttive precise salvate in `.agents/workflows/`:
- `orchestrator.md`: Coordina le operations e delega i compiti
- `task_analyzer.md`: Traduce i requisiti in step implementativi
- `python_engineer.md`: Sviluppa gli script Core di ingestion
- `ai_integrator.md`: Integra Ollama e Kokoro TTS
- `streaming_expert.md`: Ingegnere del video output (FFmpeg)
- E altri...

## ⚡ Funzionalità Chiave & Moduli Locali

### 🎙️ Integrazione Interattiva Telegram (`telegram_agent.py`)
Il sistema include un Bot Telegram interattivo per creare engagement reale con il pubblico e permettere la gestione remota:
* **Memo Vocali del Pubblico**: Gli ascoltatori possono inviare memo vocali sul canale Telegram. Il bot li scarica, li converte in formato WAV PCM a 24000Hz (mono) tramite FFmpeg e li mette in coda di approvazione per la messa in onda immediata.
* **Pannello Amministrativo Remoto**: Tramite comandi esclusivi per l'amministratore (autenticazione tramite l'username Telegram configurato via environment variable), è possibile monitorare e governare l'intera regia e lo streaming da remoto con i comandi `/status`, `/start`, `/restart` e `/stop`.

### 🎵 AI Music Worker (`ai_music_worker.py`)
Per riempire in modo creativo ed esente da copyright i momenti di silenzio o di attesa tra i programmi, il sistema integra un worker locale per la musica generativa AI (`newsica-ai-music-worker`). Questo genera tracce procedurali direttamente in locale senza costi e senza alcun rischio di strike Content ID su YouTube.

La rotazione musicale live mantiene anche una memoria persistente degli ultimi brani mandati in onda in `runtime/music_rotation_history.json`, cosi' la regia evita ripetizioni troppo ravvicinate anche dopo restart tecnici. La finestra recente e' regolabile via `MUSIC_ROTATION_RECENT_WINDOW` (default `8`).

### 🎛️ Director Runtime & Playout Events
La regia live usa ora un solo protocollo interno: il `DirectorAgent` restituisce esclusivamente `PlayoutEvent` tipizzati, che `src/director.py` esegue sequenzialmente tramite un runtime unico.

Questo elimina il vecchio doppio binario `dict` legacy + eventi e riduce i bug silenziosi in cui:
* uno slot avanzava di stato ma non metteva davvero audio in coda;
* un side effect secondario, come il trigger della generazione di nuova musica AI, si perdeva nel bridge di compatibilità;
* rami poco battuti come podcast e special broadcast divergevano dal path standard.

Il refactor include anche una protezione sui job musica AI: i job `rotation_fill` rimasti orfani in stato `running` vengono auto-chiusi dopo timeout configurabile (`AI_MUSIC_RUNNING_STALE_SECONDS`, default `3600`), così la schedulazione automatica non resta bloccata per giorni.

Il supervisor dei sotto-processi del director è ora idempotente: prima di lanciare `ticker_agent.py`, `overlay_agent.py`, `hourly_chime_agent.py`, `chat_agent.py` o `preparation_agent.py`, verifica se il processo è già vivo e in quel caso salta l'avvio duplicato. `hourly_chime_agent.py` e `preparation_agent.py` hanno inoltre ora un proprio lock singleton, per evitare doppie istanze anche fuori dal path standard del director.

In caso di restart del solo director, la regia prova anche a recuperare il contesto dello slot corrente senza ripartire dall'inizio del parlato. Se il blocco in corso era in una fase vocale non riprendibile a metà file, il director degrada in `music_rotation_until_deadline`: mantiene la fascia editoriale corrente, ma evita replay artificiali della `Parte 1` o del podcast completo.

Il restart del director è ora anche cooperativo: su `SIGTERM` o `SIGINT` la regia interrompe in modo pulito il processo audio corrente, sblocca il loop FIFO e termina con `exit 0`. Il `watchdog.sh` distingue quindi gli stop intenzionali dai crash veri, riducendo il rumore di log tipo `Broken pipe` durante deploy e riavvii tecnici.

### 🎼 Importazione Musica Creative Commons (`chart_importer.py`)
Esiste anche uno script locale per importare brani esterni in `assets/music/`, con focus primario su tracce **Creative Commons BY** recuperate da **Jamendo**. Lo script:
* scarica i file audio;
* li converte e normalizza in MP3 standard;
* genera un manifest JSON per ogni brano con titolo, artista, fonte, URL e licenza.

Uso consigliato:
```bash
venv/bin/python3 src/newsica/audio/chart_importer.py --source jamendo --limit 3
```

Opzioni principali:
* `--source jamendo`: modalità consigliata, usa brani CC-BY con licenza esplicita.
* `--source itunes`: modalità solo sperimentale, ad alto rischio copyright/Content ID.
* `--limit N`: numero massimo di brani da importare dalla chart.

Output atteso:
* file audio in `assets/music/`
* manifest affiancati `assets/music/NOME_BRANO.json`

Stato attuale dell'integrazione:
* lo script esiste ed è usabile da CLI;
* non è ancora agganciato alla Dashboard;
* la libreria musicale live oggi scansiona i file audio in `assets/music/`, ma non impone ancora un filtro rigido "solo file con manifest valido".

### 🛡️ Protezione Anti-Sleep per macOS (`caffeinate`)
NewsicaTV è progettato per lo streaming continuo H24. Su macchine macOS, all'avvio della live lo script `manage.sh` attiva automaticamente il processo nativo `caffeinate` con asserzioni a livello di kernel. Questo previene lo sleep di sistema, display e dischi rigidi, assicurando:
* Prestazioni costanti e non ridotte della GPU/MPS per la sintesi vocale TTS (Chatterbox/Kokoro).
* Banda passante e connessione RTMP a YouTube ininterrotta senza cadute di rete.
* Riavvi da remoto stabili (impedisce che il PC ritorni in stop subito dopo l'avvio via Telegram).

### 🧪 Test Prompt da Dashboard
La pagina `Tools` della dashboard include un pannello unico `Genera Evento al Volo`.

Da qui puoi selezionare il format editoriale da un dropdown e lanciare test on-demand per:
* `news`
* `flash_60s`
* `sport`
* `meteo`
* `wellness`
* `podcast`
* `breaking_news`

Il pannello usa la pipeline locale esistente e invia alla regia un playout immediato coerente con il `character_id`, cosi' overlay, ticker e stato runtime riflettono il format reale in onda.

### 📰 Gestione Fonti RSS da Dashboard
La dashboard include ora una vista `Fonti RSS` dedicata alla manutenzione del registry editoriale.

Da qui puoi:
* vedere tutte le fonti attive lette da `src/newsica/sources/registry.py`;
* aprire un'anteprima live del feed per controllare titoli e pubblicazione;
* aggiungere una nuova fonte con `id`, `url` e `category`;
* rimuovere una fonte esistente.

Le modifiche scrivono direttamente su `registry.py` e il collector rilegge il file a ogni ciclo di raccolta, quindi la regia vede i cambi senza restart manuale del processo.

## 🚀 Esecuzione e Gestione

Per semplificare l'avvio, l'arresto e il monitoraggio di tutti i servizi in locale (Dashboard, Regia, Ticker, Chime e Streamer FFmpeg), è disponibile il tool unificato **`manage.sh`** nella root del progetto.

### 🔑 Configurazione Iniziale
Rendi eseguibile lo script di gestione:
```bash
chmod +x manage.sh
```

### 📋 Comandi Rapidi

*   **Avviare tutto il sistema**:
    ```bash
    ./manage.sh start
    ```
    *Avvia la Dashboard Web (porta 5050), la regia automatica e il flusso di streaming video verso YouTube.*

*   **Verificare lo stato dei servizi**:
    ```bash
    ./manage.sh status
    ```
    *Mostra graficamente quali moduli (Web, Director, FFmpeg, Ticker, Chime, Watchdog) sono attivi e con quali PID.*

*   **Arrestare e ripulire il sistema**:
    ```bash
    ./manage.sh stop
    ```
    *Spegne in sicurezza tutti i processi attivi e rimuove i lockfile obsoleti per prevenire conflitti alla successiva esecuzione.*

*   **Riavviare l'intero flusso**:
    ```bash
    ./manage.sh restart
    ```

*   **Visualizzare i log in tempo reale**:
    ```bash
    ./manage.sh logs
    ```

*   **Verificare la salute della diretta end-to-end**:
    ```bash
    ./manage.sh live-health
    ```
    *Controlla processi locali, log Director/FFmpeg, progress RTMP, runner `screen`/`launchctl` e stato pubblico del player YouTube.*

---

## 📜 Licenza
Distribuito sotto licenza MIT. Vedi il file `LICENSE` per maggiori informazioni.
