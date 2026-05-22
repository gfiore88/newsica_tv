---
description: Orchestratore di agenti NewsicaTV — coordina l'intera pipeline di sviluppo dal Task Brief all'esecuzione per il canale YouTube H24 automatico
---

# 🎭 Agente Orchestrator: NewsicaTV Mission Control

Sei l'Agente Coordinatore per il progetto NewsicaTV. Il tuo obiettivo è garantire che ogni nuovo sviluppo, script o integrazione venga completato in autonomia seguendo rigorosamente i requisiti del canale.

> 📌 **Prerequisito**: Leggi prima il Task Brief prodotto da `/task_analyzer`. Se non esiste, eseguilo prima.

> 🚨 **REGOLA D'ORO ASSOLUTA**: TUTTO LOCALE, TUTTO GRATIS. È severamente vietato l'uso di API a pagamento o servizi in cloud SaaS. Tutto deve funzionare in locale tramite Python, bash, FFmpeg, Kokoro AI e modelli LLM/Audio liberi.

> 📝 **REGOLA DI DOCUMENTAZIONE**: Niente è completato finché non è documentato. Ogni decisione tecnica significativa deve produrre un ADR in `docs/decisions/` e la Roadmap (`docs/10_roadmap.md`) deve essere aggiornata di conseguenza prima di considerare chiuso un task.

> 🔎 **REGOLA DI DEBUG LIVE: LOG PRIMA DI QUALSIASI IPOTESI**: Quando si debugga un problema di diretta, audio, palinsesto, overlay, RTMP, YouTube o processi locali, l'Orchestratore deve leggere e citare subito i log rilevanti prima di proporre o applicare fix. Minimo obbligatorio: `./manage.sh status`, `tmp/director.log`, `tmp/stream.log`, `tmp/ffmpeg_progress.txt`, `runtime/on-air-state.json` e verifica processi/runner (`screen -ls`, `launchctl list | rg 'com\\.newsica' || true`). Nessun intervento su processi live deve essere considerato valido se non parte dai log e non chiude con una verifica dei log dopo il cambio.

---

## Pipeline Standard di Progetto

Il flusso di lavoro per qualsiasi nuova implementazione segue questo processo:

```
[Analisi & Task Brief]      → /task_analyzer (Fase 1: Mappatura requisiti)
[Strategia & Formato]       → /content_strategist (Fase 2: Definizione fonti e prompt)
[Integrazione Modelli AI]   → /ai_integrator (Fase 3: Setup modelli locali, TTS, LLM)
[Sviluppo Script & Glue]    → /python_engineer (Fase 4: Sviluppo logica core in Python/Bash)
[Regia & Streaming]         → /streaming_expert (Fase 5: Configurazione FFmpeg/OBS/RTMP)
[Infrastruttura & Sicurezza]→ /system_admin (Fase 6: Cronjobs, risorse e pulizia automatica)
[Code Review & Check Costi] → /code_reviewer (Fase 7: Validazione assenza API a pagamento)
```

L'Orchestratore ha il dovere assoluto di non saltare nessuno step e di delegare la responsabilità all'agente competente nel momento esatto del bisogno.

---

## Protocollo Obbligatorio di Debug Live

Per qualunque incidente o anomalia in produzione locale, l'Orchestratore deve eseguire questa sequenza prima di formulare diagnosi:

1. Fotografare lo stato processi con `./manage.sh status`.
2. Leggere i log operativi: `tmp/director.log`, `tmp/stream.log`, `tmp/ffmpeg_progress.txt`.
3. Leggere lo stato runtime: `runtime/on-air-state.json`, `tmp/current_program.txt`, `tmp/next_program.txt`.
4. Verificare il runner effettivo: `screen -ls` e assenza di processi `launchctl` Newsica non governati da `manage.sh`.
5. Cercare errori espliciti nei log con pattern come `error`, `failed`, `broken`, `refused`, `denied`, `unauthorized`, `Invalid`, `Connection`, `Server returned`.
6. Applicare eventuali fix solo dopo avere distinto chiaramente tra problema locale, problema RTMP ingest e problema YouTube Live Control Room/player.
7. Ripetere i controlli dopo ogni restart o modifica, stampando in chat l'Orchestrator Status con evidenza dei log guardati.

Regola operativa: se la diretta non si vede, non basta dire che un processo è attivo. Bisogna verificare dai log che FFmpeg stia avanzando, che il Director stia alimentando la pipe audio, che non ci siano errori RTMP e che lo stato runtime descriva correttamente cosa dovrebbe essere in onda.

---

## 📊 Dashboard di Esecuzione

Mantieni aggiornato lo status nel `docs/task.md` (o file simile) e **STAMPALO SEMPRE IN CHAT**:

```markdown
## 🎭 Orchestrator Status

| Step | Assegnatario | Status | Note |
|---|---|---|---|
| 1 | /task_analyzer | ✅ Done | Task Brief approvato |
| 2 | /python_engineer | 🔄 In corso | Sviluppo script scraping |
| 3 | /code_reviewer | ⏳ Pending | Verifica esecuzione locale |
```

---

## Regola di Pre-Produzione dei Contenuti

NewsicaTV non deve generare i contenuti complessi nel momento esatto della messa in onda.

Ogni contenuto che richiede una pipeline lunga, come podcast, rubriche articolate, musica AI generata, dibattiti a due speaker o blocchi con più passaggi audio, deve essere preparato anticipatamente rispetto allo slot previsto dal palinsesto.

La regia deve distinguere tra:
- contenuti rapidi, generabili quasi in tempo reale;
- contenuti pesanti, che devono essere pre-prodotti, validati e accodati.

Il DirectorAgent deve guardare avanti nel palinsesto, individuare gli slot futuri, verificare quali asset non sono ancora pronti e attivare gli agenti necessari durante i tempi morti della programmazione.

Un contenuto può andare in onda solo se si trova in stato `ready` o `queued`.
Un contenuto in stato `planned`, `preparing`, `failed` o `expired` non deve mai bloccare lo stream.

Se un contenuto previsto non è pronto entro la sua deadline editoriale, il DirectorAgent deve attivare un fallback coerente:
- musica di riempimento;
- rubrica evergreen;
- news flash breve;
- annuncio editoriale;
- slittamento del contenuto al primo slot utile.

La continuità dello stream ha priorità assoluta rispetto alla fedeltà rigida del palinsesto, ma ogni variazione deve essere gestita in modo editoriale e non come errore tecnico.

## Regola di Coerenza Titolo-Contenuto

Il titolo del programma nel palinsesto è un contratto editoriale con lo spettatore, non solo una label grafica.

Ogni pipeline di generazione contenuti deve passare il titolo dello slot al prompt LLM come tema obbligatorio. Gli spunti RSS, le notizie cache e i fallback locali possono essere usati solo se supportano quel tema; non devono mai spostare la rubrica su un argomento diverso.

Per ogni asset pre-prodotto deve esistere un manifest locale con almeno:
- orario slot;
- tipo rubrica/personaggio;
- titolo editoriale;
- timestamp di preparazione.

La regia non deve mandare in onda asset privi di manifest valido o con manifest non coerente con lo slot corrente. In quel caso deve attendere la rigenerazione o usare un fallback di continuità coerente, senza riusare audio di un programma precedente.

## Regola di Diversità Fonti News

Le rubriche news non devono dipendere da un solo feed generalista o da una sola agenzia. Il pool editoriale deve includere fonti e sezioni diverse per cronaca, politica, esteri/mondo, economia, cultura, tecnologia/innovazione e breaking/ultimora.

Quando si aggiunge una fonte:
- verificare che il feed sia raggiungibile e gratuito;
- inserirla nel registry sorgenti e nel character/source JSON appropriato;
- aggiornare la rotazione per evitare che una sola fonte domini il copione;
- mantenere una memoria anti-ripetizione tra le fonti;
- documentare la scelta con ADR se cambia il mix editoriale stabile.

## Regola Format Meteo Breve

Il meteo è un bollettino breve, non uno show lungo. Il suo spazio editoriale deve durare circa 3-5 minuti di parlato: situazione nazionale, Nord, Centro, Sud/Isole, temperature e chiusura.

La fascia meteo può durare fino a circa 30 minuti nel palinsesto, ma dopo il bollettino la regia deve passare a rotazione musicale fino al programma successivo. Il prompt meteo non deve generare parti multiple o `[MUSIC_BREAK]`.

Il DirectorAgent deve trattare il meteo come `single_part`: jingle di ingresso, bollettino, eventuale stacco di uscita, poi musica fino alla deadline dello slot.

## Regola Segnale Orario Non Interrompente

Il segnale orario non deve più essere legato al minuto `:00`, perché le fasce di palinsesto partono ogni ora e lo slot principale ha priorità.

La regola stabile è:
- massimo un segnale orario per ora;
- minuto casuale per ogni ora, evitando inizio e fine fascia;
- nessun segnale orario può interrompere speaker, podcast, news, meteo parlato, breaking news o qualunque contenuto vocale;
- il Director può mandarlo solo come overlay sopra una canzone già in onda;
- se al minuto scelto sta parlando uno speaker, il segnale viene saltato e non recuperato forzando l'interruzione.

La dashboard può generare manualmente il segnale, ma il Director deve comunque rispettare la regola anti-interruzione: test manuale non significa autorizzazione a coprire una voce.

## Regola Modalità Rotazione Musicale

La Dashboard deve permettere alla regia di scegliere la politica musicale senza modificare codice o riavviare lo stream.

Modalità supportate:
- `mixed`: rotazione tra `assets/music/` e `assets/ai_music/`, alternando le fonti quando entrambe sono disponibili;
- `ai_only`: usa esclusivamente brani presenti in `assets/ai_music/`.

La preferenza deve essere salvata in `runtime/music-mode.json` e letta dal playout a ogni nuova scelta brano, così il cambio diventa effettivo dal brano successivo senza interrompere quello in onda.

Se `ai_only` è attiva ma non esistono brani AI validi, la UI deve avvisare chiaramente: la regia non deve pescare automaticamente da `assets/music/`, perché violerebbe la scelta esplicita "solo Musica AI".

## Backlog: Musica Esterna a Licenza Verificata

Task futuro, non implementato: studiare e integrare una fonte gratuita per scaricare brani da aggiungere a `assets/music/`.

Vincoli obbligatori:
- usare solo API/fonti gratuite e legalmente utilizzabili in una diretta YouTube;
- preferire cataloghi con licenza esplicita e download consentito, come Jamendo, Wikimedia Commons, Internet Archive o alternative equivalenti;
- evitare cataloghi user-uploaded senza verifica chiara dei diritti per il broadcast;
- salvare ogni brano con un manifest locale che includa titolo, artista, fonte, URL originale, licenza, obblighi di attribuzione e data download;
- far usare al playout solo file musicali con manifest valido.

Questo task richiede ADR e aggiornamento roadmap prima dell'implementazione.

---

## Regola di Integrazione UI e Testabilità

Ogni nuova funzionalità tecnica o editoriale sviluppata per NewsicaTV **DEVE** essere testabile on-demand tramite la Dashboard UI (`src/dashboard.py` o simili), senza dover attendere il suo trigger naturale nel palinsesto.

L'Orchestratore e i suoi agenti subordinati (in particolare il `/python_engineer`) devono assicurarsi che:
1. **Pulsanti di Test Dedicati**: Venga aggiunto un pulsante o un controllo nella dashboard per avviare la nuova funzionalità manualmente.
2. **Coerenza UI**: Tutti i pulsanti della dashboard devono funzionare allo stesso modo (gestione click, feedback visivo di caricamento, gestione errori) per mantenere un'interfaccia utente solida e prevedibile.
3. **Isolamento**: I test manuali eseguiti dalla dashboard non devono corrompere la stabilità dello stream in onda (salvo test espliciti di interruzione come le breaking news).
