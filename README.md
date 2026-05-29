# 📺 NewsicaTV

**NewsicaTV** è un sistema di broadcasting automatico sperimentale. L'obiettivo del progetto è generare e streammare un canale televisivo/radiofonico su YouTube Live H24, gestito interamente da Agenti AI e tool **100% locali**.

Il progetto segue due vincoli fondamentali:
1. **Zero Costi**: Nessun utilizzo di API a pagamento o servizi Cloud (es. OpenAI, ElevenLabs).
2. **Local-First**: Tutti i processi (scraping, LLM per rielaborazione testi, TTS, mix audio e regia video) devono girare localmente sulla macchina host.

Il codice deve restare pubblicabile e riusabile: credenziali, stream key, URL VPS, token, host SSH, username, path assoluti di produzione e qualunque valore personale devono stare in `.env` o in configurazioni private escluse dal repository. Non vanno hardcodati nel codice.

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

### 🧠 Generazione Contenuti Local/Remote (`NEWSICA_GENERATION_MODE`)
La pipeline di pre-produzione passa da un contratto unico di generazione, così il comportamento full local resta il default e un futuro deployment ibrido VPS+Mac potrà usare adapter remoti senza duplicare la logica editoriale.

Configurazione attuale:
```bash
NEWSICA_GENERATION_MODE=local
```

La modalità `remote` è riservata all'implementazione ADR 0051 e richiederà variabili private come `NEWSICA_REMOTE_GENERATION_URL`, `NEWSICA_REMOTE_GENERATION_TOKEN`, worker id, polling, heartbeat e parametri di trasporto. Questi valori devono restare fuori dal codice e dal repository pubblico.

Variabili operative previste:
```bash
NEWSICA_GENERATION_MODE=local
NEWSICA_RUN_GENERATION_WORKER=false
NEWSICA_REMOTE_GENERATION_QUEUE=http
NEWSICA_REMOTE_WORKER_TRANSPORT=http
NEWSICA_REMOTE_GENERATION_URL=https://vps.example.invalid
NEWSICA_REMOTE_GENERATION_TOKEN=...
NEWSICA_REMOTE_WORKER_ID=mac-worker-1
NEWSICA_REMOTE_POLL_SECONDS=10
NEWSICA_REMOTE_IDLE_POLL_SECONDS=30
NEWSICA_REMOTE_STALE_SECONDS=300
NEWSICA_REMOTE_HTTP_TIMEOUT_SECONDS=30
NEWSICA_REMOTE_MAX_UPLOAD_MB=512
NEWSICA_REMOTE_INCOMING_RETENTION_SECONDS=86400
NEWSICA_RUNTIME_ASSETS_DIR=runtime/assets
NEWSICA_VPS_HOST=vps.example.invalid
NEWSICA_VPS_SSH_USER=root
NEWSICA_VPS_SSH_PORT=22
NEWSICA_VPS_SSH_KEY_PATH=~/.ssh/newsica_vps
NEWSICA_VPS_REMOTE_APP_DIR=/opt/newsica_tv
```

In modalita' `remote`, il VPS accoda job remoti ma non deve eseguire workload AI pesanti. `./manage.sh start` avvia `src/generation_worker.py` solo se `NEWSICA_RUN_GENERATION_WORKER=true`, valore da usare sul Mac worker e non sul VPS runtime. Il worker supporta `NEWSICA_REMOTE_WORKER_TRANSPORT=sqlite` per sviluppo co-located e `NEWSICA_REMOTE_WORKER_TRANSPORT=http` per polling verso le API del VPS. Il token remoto deve essere configurato in env e inviato come Bearer token; non esistono credenziali di default nel codice.

Le credenziali del provider VPS non devono mai entrare nel codice o in `.env.example`. La password `root` iniziale va usata solo per il bootstrap: installare una chiave SSH, aggiornare il sistema, creare la configurazione privata sul VPS, poi ruotare la password e disabilitare il login SSH via password appena possibile. Il repository pubblico deve contenere solo placeholder e default locali non sensibili.

Il trasporto HTTP remoto include anche upload multipart degli artifact verso il VPS:
- `slot_audio`: upload in `runtime/assets/incoming/{job_id}`, validazione manifest, pubblicazione atomica in `runtime/assets/ready/{slot_id}`;
- `ai_music`: upload in staging e pubblicazione in `runtime/assets/ai_music`.

Il VPS non considera un artifact pronto finche' manifest e file non sono stati validati.

La Dashboard espone anche:
- `GET /api/generation/summary` per conteggi, worker attivi e ultimi job;
- `POST /api/generation/incoming/cleanup` per pulire staging vecchi, protetto dallo stesso token remoto.

### 🚀 Deploy VPS con GitHub Actions

Il deploy produzione e' separato dalla CI. La CI gira su push/PR e verifica backend, lint e build frontend; il deploy VPS e' manuale tramite workflow `Deploy VPS`, cosi' un push non riavvia automaticamente la diretta.

Secret GitHub richiesti nell'environment `production-vps`:

```bash
VPS_HOST=your-vps-ip-or-hostname
VPS_USER=newsica
VPS_PORT=22
VPS_APP_DIR=/opt/newsica_tv
VPS_SSH_PRIVATE_KEY=<private key authorized on the VPS>
NEWSICA_VPS_ENV_B64=<optional base64 of the private VPS .env>
```

Il deploy usa `scripts/deploy_vps.sh` via `rsync` ed esclude sempre `.env`, `runtime/`, `tmp/`, `assets/`, virtualenv, `node_modules`, cache e modelli pesanti. In questo modo codice e dipendenze vengono aggiornati senza cancellare DB, asset pronti, log o credenziali del server.

Prerequisito VPS per la build frontend: Node.js 20+; sul server di produzione e' consigliato Node.js 22 LTS.

Per esporre la dashboard su dominio pubblico si usa nginx come reverse proxy verso Flask:

```bash
NEWSICA_DOMAIN=regia.newsicatv.it
NEWSICA_ADMIN_EMAIL=admin@example.com
NEWSICA_DASHBOARD_HOST=127.0.0.1
NEWSICA_DASHBOARD_PORT=5050
```

Quando il record DNS `A` punta al VPS, configurare nginx:

```bash
ssh -i ~/.ssh/newsica_vps newsica@your-vps
cd /opt/newsica_tv
NEWSICA_DOMAIN=regia.newsicatv.it NEWSICA_ENABLE_TLS=false bash scripts/configure_vps_nginx.sh
```

Dopo la propagazione DNS, abilitare HTTPS:

```bash
NEWSICA_DOMAIN=regia.newsicatv.it NEWSICA_ADMIN_EMAIL=admin@example.com NEWSICA_ENABLE_TLS=true bash scripts/configure_vps_nginx.sh
```

In produzione la porta `5050` non deve restare pubblica: nginx espone solo `80/443` e proxy verso `127.0.0.1:5050`.

Modalita' workflow:
- `none`: copia codice, installa dipendenze, builda frontend, fa check sintattici e mostra status senza avviare/riavviare;
- `start`: come sopra, poi `./manage.sh start`;
- `restart`: come sopra, poi `./manage.sh restart`, quindi interrompe brevemente la diretta.

Per il primo deploy si puo' creare `.env` direttamente sul VPS oppure impostare `NEWSICA_VPS_ENV_B64` come secret. Esempio locale per generare il valore:

```bash
base64 -i .env | pbcopy
```

Prima di usare quel valore in produzione, adattare la `.env` VPS: `NEWSICA_GENERATION_MODE=remote`, URL pubblica del VPS, token remoto, stream key e tutte le credenziali operative devono restare private.

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
