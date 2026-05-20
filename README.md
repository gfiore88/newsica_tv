# 📺 NewsicaTV

**NewsicaTV** è un sistema di broadcasting automatico sperimentale. L'obiettivo del progetto è generare e streammare un canale televisivo/radiofonico su YouTube Live H24, gestito interamente da Agenti AI e tool **100% locali**.

Il progetto segue due vincoli fondamentali:
1. **Zero Costi**: Nessun utilizzo di API a pagamento o servizi Cloud (es. OpenAI, ElevenLabs).
2. **Local-First**: Tutti i processi (scraping, LLM per rielaborazione testi, TTS, mix audio e regia video) devono girare localmente sulla macchina host.

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
