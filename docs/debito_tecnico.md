# 📓 Registro dei Debiti Tecnici e Feature Pendenti (NewsicaTV)

Questo documento raccoglie in modo strutturato tutti i **debiti tecnici**, le **fasi di refactoring rimaste appese** e le **feature della Roadmap (MVP 3 & MVP 4)** non ancora implementate. 

L'obiettivo è fornire un archivio chiaro e azionabile con checklist per le lavorazioni future, mantenendo fermo il principio cardine: **Tutto locale, tutto gratuito (Zero Cloud).**

---

## 🧩 1. Refactoring & Architettura Python

### 📻 A. Playout Event Planner (ADR 0019 - Refactor Fase 3b)
La logica di riproduzione audio regolare è in `playout.py`, ma il sequenziamento (rubrica classica vs show multi-part) è hardcoded nel thread generatore di `director.py` tramite controlli semaforici (`is_multipart.txt`).
- [x] **Sviluppare un PlayoutPlanner a Eventi:** Creare una classe o un modulo che traduca il blocco del palinsesto corrente in una sequenza ordinata di oggetti evento polimorfici:
  ```python
  class PlayJingle(PlayoutEvent): ...
  class PlayVoicePart(PlayoutEvent): ...
  class PlayMusicTrack(PlayoutEvent): ...
  class UpdateOverlay(PlayoutEvent): ...
  ```
- [x] **Decoppiare il Generatore dalla Coda:** Il generatore deve inserire eventi nella coda del Playout, e il Playout deve processarli sequenzialmente.
- [x] **Rimuovere dipendenze semaforiche dirette** come `is_multipart.txt` a favore di metadati strutturati negli eventi.

### ✂️ B. Riduzione e Semplificazione di `director.py` (ADR 0016 - Refactor Fase 4)
Attualmente `src/director.py` è un file monolitico di oltre 800 righe che fa da supervisore, gestore di rete, controllore FIFO, generatore di segnale orario e player audio sincrono.
- [x] **Spostare la gestione del palinsesto (Schedule):** Creare `src/newsica/broadcast/scheduler.py` per gestire l'avanzamento delle fasce orarie e i calcoli delle deadline.
- [x] **Spostare la gestione dei file di controllo e overlay:** Creare `src/newsica/broadcast/overlay.py` per isolare la scrittura di `STATE_FILE`, `PROGRAM_FILE`, `NEXT_PROGRAM_FILE` e i file degli accenti colore.
- [x] **Spostare la supervisione dei sotto-processi:** Creare un modulo per avviare e monitorare thread o processi secondari (come il ticker).
- [x] **Obiettivo finale:** Portare `director.py` sotto le **250 righe di codice** per lasciarlo come puro orchestratore ad alto livello.
- [x] **Rimozione bridge legacy dict/eventi:** completata la migrazione a `PlayoutEvent` unificati per evitare divergenze tra path live e path planner.
- [ ] **Unit Testing:** Implementare test unitari sul planner e sul selettore di notizie simulando la pipeline senza dover avviare FFmpeg.
- [ ] **Estensione copertura test regressivi:** Costruire progressivamente una suite piu' ampia di unit test sui rami critici della regia live (`director.py`, breaking news, restore slot, control bus, scheduler, playout state). Nota operativa: il bisogno e' riconosciuto e documentato, ma questo non e' un task da svolgere ora; va pianificato come cantiere dedicato per non rallentare i fix runtime prioritari.
- [ ] **Allineamento Dashboard ai nuovi flussi del Director:** La Dashboard oggi e' compatibile con il runtime refactorato, ma non rappresenta ancora in modo nativo gli stati e i flussi introdotti dal nuovo director (`SPECIAL_BROADCAST`, `breaking_news`, `podcast_immediate`, `telegram_voice`, recovery post-restart, restart servizi coerenti, semantica reale del palinsesto attivo). Va aperto un task dedicato per riallineare UI, API e semantica operativa al modello attuale della regia. Nota operativa: documentato come debito tecnico, ma non da implementare ora.

---

## 🧠 2. Automazione AI & Agenti (Locali e Gratuiti)

### 🎵 A. Generatore di Musica AI Locale (ADR 0020)
Il caricamento e l'alternanza dei brani da `assets/ai_music/` sono pronti in `MusicLibrary`, ma manca il motore di generazione.
- [x] **Integrazione ACE-Step v1.5:** Creare uno script di background (es. `src/newsica/audio/music_generator.py` o analogo bash) che utilizzi ACE-Step localmente.
- [x] **Generazione offline:** Lo script deve generare in anticipo brani da 30-60 secondi nei momenti di minore carico della CPU (o come task schedulato).
- [x] **Pipeline di normalizzazione:** Convertire e normalizzare l'audio generato (16-bit PCM, 24kHz o 44.1kHz mono/stereo coerente) prima di salvarlo in `assets/ai_music/` per evitare sbalzi di volume o frequenza in onda.
- [x] **History anti-ripetizione persistente:** `MusicLibrary` salva gli ultimi brani andati in onda in `runtime/music_rotation_history.json`, registra gli eventi di esclusione in `runtime/music_rotation_blocks.json`, evita di sporcare la history durante i tentativi dry-run e preferisce candidati freschi quando il pool lo consente.

### 🚨 B. Agente Breaking News Autonomo (MVP 3)
Il meccanismo di interruzione sincrona a "zero buchi" è stabile nel regista, ma l'innesco è prettamente manuale dalla Dashboard.
- [x] **Sviluppare il calcolo dello score d'urgenza:** Creare in `src/breaking_news_agent.py` una logica che valuti le notizie fresche in cache (`tmp/raw_news.json`) calcolando un punteggio:
  $$\text{score} = \text{freschezza} + \text{peso\_fonte} + \text{parole\_chiave} - \text{duplicati}$$
- [x] **Demone di Ingestion periodico:** Eseguire in background un controllo periodico (es. ogni 10-15 minuti) sulle fonti ANSA Ultim'ora.
- [x] **Autotrigger:** Se una notizia supera una certa soglia di score, l'agente deve generare autonomamente il bollettino audio e inviare il segnale `BREAKING_NEWS_READY` per interrompere immediatamente il flusso regolare del regista.

### 📅 C. Motore di Palinsesto Giornaliero Dinamico (MVP 3)
- [x] **Fasce e formati flessibili:** `EditorialDirectorAgent` genera ora scalette diverse usando `get_weekly_appointments` (es. weekend e speciali settimanali).
- [x] **Generazione dinamica dei titoli delle rubriche:** Implementato in `EditorialDirectorAgent.generate_dynamic_schedule` usando Ollama per inventare titoli sempre nuovi attorno ai pillar giornalieri.

### 🔍 D. Fact-Checking & Anti-Allucinazione (MVP 3)
Manca un filtro di validazione editoriale prima della messa in onda dei copioni generati dall'LLM locale.
- [ ] **Filtro di veridicità e duplicazione:** Sviluppare un modulo (`src/newsica/editorial/fact_checker.py`) per verificare che i fatti descritti dall'LLM corrispondano a dati reali presenti nelle fonti originarie.
- [ ] **Tracciamento trasparente delle fonti:** Salvare in un archivio strutturato (`archive/aired_log.json`) i link e le agenzie che hanno generato ciascun blocco parlato andato in onda, a scopo di debug e disclosure per le policy di YouTube.

---

## 📺 3. Broadcaster & Regia Video

### 🎨 A. Ripristino Accenti Colore Dinamici in Regia (ADR 0012)
- [x] **Integrazione Grafica Overlay:** Il cambio di accento colore nei file in `tmp/accent_*.txt` è pronto, e l'overlay video di FFmpeg (in `overlay_agent.py`) ricolora dinamicamente i box grafici (ULTIMORA, orologio, box del programma) in base al blocco in onda letto da `on-air-state.json`.

---

## 🖥️ 4. Infrastruttura e Gestione Processi

### 🐕 Conflitto tra Daemon System-Level (launchd) e Script di Gestione (manage.sh)
- [x] **Debito Risolto (2026-05-20):** La presenza di file plist ereditati/sperimentali in `.agents/launchd/` caricati nel database `launchd` di macOS generava istanze duplicate della Regia e dello Streamer ogni 10 secondi (con `Parent PID: 1`). Queste istanze entravano in collisione con quelle ufficiali lanciate da `./manage.sh` tramite `watchdog.sh`, riempiendo `director.log` di errori di singleton.
- [ ] **Linee Guida Future:** 
  - Evitare l'avvio manuale in parallelo a launchd.
  - Se si desidera utilizzare launchd per la stabilità in produzione H24, integrare l'abilitazione/disabilitazione dei plist direttamente dentro `./manage.sh` (es. `./manage.sh daemon-enable` e `./manage.sh daemon-disable`) anziché usare loop di background shell orfani.
