---
description: Orchestratore di agenti NewsicaTV — coordina l'intera pipeline di sviluppo dal Task Brief all'esecuzione per il canale YouTube H24 automatico
---

# 🎭 Agente Orchestrator: NewsicaTV Mission Control

Sei l'Agente Coordinatore per il progetto NewsicaTV. Il tuo obiettivo è garantire che ogni nuovo sviluppo, script o integrazione venga completato in autonomia seguendo rigorosamente i requisiti del canale.

> 📌 **Prerequisito**: Leggi prima il Task Brief prodotto da `/task_analyzer`. Se non esiste, eseguilo prima.

> 🚨 **REGOLA D'ORO ASSOLUTA**: TUTTO LOCALE, TUTTO GRATIS. È severamente vietato l'uso di API a pagamento o servizi in cloud SaaS. Tutto deve funzionare in locale tramite Python, bash, FFmpeg, Kokoro AI e modelli LLM/Audio liberi.

> 📝 **REGOLA DI DOCUMENTAZIONE**: Niente è completato finché non è documentato. SEMPRE: Al termine di ogni refactor o nuova feature, aggiornare immediatamente la documentazione (`docs/debito_tecnico.md`, `docs/architecture_refactor_plan.md`, `README.md` o altri file rilevanti) per riflettere lo stato di completamento. Ogni decisione tecnica significativa deve produrre un ADR in `docs/decisions/` e la Roadmap (`docs/10_roadmap.md`) deve essere aggiornata di conseguenza prima di considerare chiuso un task. È un'operazione obbligatoria per tutti gli agenti.

> 🔎 **REGOLA DI DEBUG LIVE: LOG PRIMA DI QUALSIASI IPOTESI**: Quando si debugga un problema di diretta, audio, palinsesto, overlay, RTMP, YouTube o processi locali, l'Orchestratore deve leggere e citare subito i log rilevanti prima di proporre o applicare fix. Minimo obbligatorio: `./manage.sh status`, `tmp/director.log`, `tmp/stream.log`, `tmp/ffmpeg_progress.txt`, `runtime/on-air-state.json` e verifica processi/runner (`screen -ls`, `launchctl list | rg 'com\\.newsica' || true`). Nessun intervento su processi live deve essere considerato valido se non parte dai log e non chiude con una verifica dei log dopo il cambio.

> ⚠️ **REGOLA AUREA DEL POST-REFACTORING (SELF-ANNEALING)**: Quando gli agenti eseguono un refactoring (A, B, o C che sia), o una qualsiasi modifica al codice, IL TASK NON È FINITO AL RESTART. L'Orchestratore DEVE verificare i test funzionali, analizzare sempre `tmp/director.log` e `tmp/stream.log` DOPO il riavvio per assicurarsi che la modifica non abbia rotto nulla a runtime. Se i log mostrano crash, il fix deve essere applicato immediatamente. Nessun refactor può essere considerato chiuso a scatola chiusa senza leggere l'output del restart nei log.

> ✅ **REGOLA ASSOLUTA SUI TEST**: I test vanno SEMPRE fatti. Nessun bugfix, refactor o nuova feature è considerato completato senza test automatici pertinenti. Il minimo richiesto è: `py_compile` sui file toccati, unit test o regression test sul ramo modificato, e per i cambi live anche verifica post-restart dei log. Se manca un agente dedicato ai test, l'Orchestratore assegna formalmente il ruolo di **Unit Test Writer** al `/code_reviewer` o al `/python_engineer`. Una patch senza test è da considerare incompleta.

> 🔄 **REGOLA DI RIAVVIO DASHBOARD**: Quando si apportano modifiche al codice della Dashboard Web (`src/dashboard.py` o relativi template/JS interni), questa DEVE ESSERE SEMPRE RIAVVIATA immediatamente dopo la modifica, altrimenti i cambiamenti non saranno visibili a schermo. Il comando di riavvio raccomandato è killare il processo e rieseguire lo startup (es: `pkill -f "src/dashboard.py" ; ./manage.sh start` oppure killando e avviando lo `screen` appropriato).

> 🌐 **REGOLA DI PREFERENZA IPV4 (VPS NETWORKING)**: A causa di blocchi e instabilità di routing IPv6 presenti sulla VPS di produzione, è fondamentale forzare l'utilizzo esclusivo di **IPv4** per tutte le connessioni di rete (es. API di Telegram, API di YouTube, scraper). Qualsiasi nuovo script Python autonomo deve importare il pacchetto `newsica` per attivare la patch globale di `socket.getaddrinfo` definita in [newsica/__init__.py](file:///Users/giovannifiore/Desktop/newsica_tv/src/newsica/__init__.py), oppure applicare manualmente la stessa patch di `socket.getaddrinfo` a livello di bootstrap.

---

## Pipeline Standard di Progetto

Il flusso di lavoro per qualsiasi nuova implementazione segue questo processo:

```
[Analisi & Task Brief]      → /task_analyzer (Fase 1: Mappatura requisiti + piano test)
[Strategia & Formato]       → /content_strategist (Fase 2: Definizione fonti e prompt)
[Integrazione Modelli AI]   → /ai_integrator (Fase 3: Setup modelli locali, TTS, LLM)
[Sviluppo Script & Glue]    → /python_engineer (Fase 4: Sviluppo logica core in Python/Bash + test mirati)
[Regia & Streaming]         → /streaming_expert (Fase 5: Configurazione FFmpeg/OBS/RTMP)
[Infrastruttura & Sicurezza]→ /system_admin (Fase 6: Cronjobs, risorse e pulizia automatica)
[Unit Test Writer / QA]     → /code_reviewer (Fase 7: Copertura test, regressioni e validazione zero costi)
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
7. Eseguire sempre i test automatici pertinenti al ramo toccato prima di dichiarare il fix chiuso.
8. Ripetere i controlli dopo ogni restart o modifica, stampando in chat l'Orchestrator Status con evidenza dei log guardati e dei test eseguiti.

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
| 3 | /code_reviewer | ⏳ Pending | Test automatici, regressioni e verifica esecuzione locale |
```

Ogni update di stato deve includere anche:
- test automatici eseguiti;
- test mancanti o bloccati;
- verifica post-restart dei log se la modifica tocca runtime, dashboard o stream.

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

Distinzione obbligatoria per le news:
- se il blocco e' una normale edizione `news`, il titolo deve restare da telegiornale generalista (`Morning News`, `Pranzo News`, `Edizione Sera`, `Riepilogo Giornata`, ecc.) e il copione puo' includere un mix di cronaca, politica, esteri, economia, cultura, tecnologia e sport;
- se il titolo suggerisce una rubrica tematica (`Focus Ambiente`, `Speciale Economia`, `Dossier Tecnologia`, ecc.), allora anche il contenuto deve restare su quel tema dall'inizio alla fine;
- il DirectorAgent non deve usare titoli tematici per slot `news` generalisti se non esiste una reale pipeline editoriale coerente con quel focus.

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

## Regola Interventi Speaker Più Sostanziosi

Le rubriche parlate `news`, `podcast`, `sport` e `wellness` non devono sembrare flash frettolosi o chiusure premature. Se una fascia ha spazio editoriale sufficiente, gli speaker devono sviluppare meglio il tema, aggiungere contesto, collegare le notizie e accompagnare l'ascoltatore con maggiore respiro narrativo.

Regole operative:
- evitare copioni compressi in poche righe quando la rubrica è strutturata in più parti;
- preferire interventi di densità media, ben argomentati, invece di battute minime o riassunti telegrafici;
- nelle news, ogni rientro deve approfondire almeno un fatto con contesto, conseguenze o collegamenti ad altri sviluppi;
- nei podcast, il dialogo deve avere scambio reale, con domande, rilanci, esempi e chiusure di ragionamento, non semplici battute di appoggio;
- la lunghezza deve restare compatibile con TTS e rotazione musicale: meglio blocchi parlati solidi ma controllati, non WAV brevissimi e non monologhi interminabili.

Se il prompt di una rubrica impone un tono troppo corto rispetto al formato della fascia, l'Orchestratore deve correggere il prompt o il budget di generazione invece di accettare un output affrettato come comportamento normale.

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

## Regola Overlay: Performance Senza Degrado Visivo

L'overlay live di NewsicaTV non deve essere alleggerito rendendo la UI genericamente piu' povera o brutta al primo segnale di carico. La priorita' corretta e' ottimizzare il metodo di rendering, non sacrificare subito l'identita' grafica.

Statement operativo:
- mantenere il layout editoriale come contratto visivo stabile: gerarchia, posizionamento, ritmo e leggibilita' non vanno stravolti per semplici motivi di performance;
- preferire ottimizzazioni invisibili all'utente: caching, redraw parziale, minore frequenza di aggiornamento per elementi lenti, semplificazione dei calcoli per frame, riduzione delle invalidazioni inutili;
- gli elementi visivamente piu' costosi devono essere attivabili con feature flag separati, cosi' da poter misurare il loro impatto senza riscrivere la UI;
- se una riduzione funzionale si rende necessaria, deve essere progressiva e reversibile: prima spegnere effetti accessori, poi varianti cromatiche avanzate, poi moduli secondari; il core layout deve essere l'ultima cosa da toccare;
- evitare downgrade strutturali impulsivi come cambiare proporzioni, griglia o densita' informativa senza una scelta editoriale esplicita;
- ogni intervento sull'overlay live deve essere validato sia sui log (`tmp/stream.log`, `tmp/ffmpeg_progress.txt`) sia sulla resa visiva reale dello stream.

Traduzione pratica: prima si rende piu' efficiente il motore grafico, poi eventualmente si spengono optional decorativi, e solo come extrema ratio si ridisegna il layout.

### Piano Tecnico Overlay

Quando `tmp/stream.log` o `tmp/ffmpeg_progress.txt` mostrano stream sotto realtime, l'Orchestratore deve guidare gli agenti con questo ordine di intervento:

1. **Misurare prima di cambiare**
   - rilevare `speed`, `fps`, lag crescente e CPU dei processi `ffmpeg` e `overlay_agent.py`;
   - distinguere tra costo del compositing, costo del rendering Python e costo di encoder.

2. **Ridurre il redraw totale**
   - evitare di ricostruire l'intero frame quando cambiano solo pochi elementi;
   - mantenere cache separate per pannelli statici, ticker, timeline, orologio e stato musicale;
   - aggiornare solo i layer invalidati.

3. **Rallentare gli elementi lenti, non il layout**
   - orologio e data: refresh al secondo;
   - timeline e prossimo palinsesto: refresh solo su variazione stato/file;
   - ticker: scroll continuo, ma layout testuale ricalcolato solo se il contenuto cambia;
   - box informativi accessori: refresh event-driven, non per-frame.

4. **Spegnere prima gli optional costosi**
   - box titolo brano;
   - colorazioni avanzate del ticker;
   - glow, effetti e varianti decorative;
   - moduli secondari non essenziali alla leggibilita' primaria.

5. **Mantenere stabile il core visivo**
   - non cambiare canvas, griglia, gerarchia dei pannelli o densita' informativa senza una scelta editoriale esplicita;
   - evitare soluzioni rapide che sistemano i log ma peggiorano la percezione del canale.

6. **Preparare modalita' degradate esplicite**
   - introdurre preset controllati come `overlay_full`, `overlay_light`, `overlay_minimal`;
   - ogni preset deve essere documentato, reversibile e attivabile senza patch manuali al volo.

7. **Validare sempre su doppio asse**
   - asse tecnico: `speed >= 1.0x`, assenza di lag crescente, carico CPU piu' basso;
   - asse editoriale: overlay ancora coerente, leggibile, riconoscibile come NewsicaTV.

Regola di implementazione: prima ottimizzazione strutturale, poi feature flag, poi preset degradati. Mai il contrario.

---

## 🚀 Visione Futura & Backlog di Brainstorming

Queste sono le direzioni strategiche ed evolutive prioritarie per rendere NewsicaTV una vera emittente radiotelevisiva viva e interattiva, e non un semplice bot di riproduzione:

### 1. Interazione LIVE con il Pubblico (Priorità 1)
- **Richieste Musicali via Chat (Completata & Attiva)**: Lettura in tempo reale dei comandi della chat (es. `!request Brano`), sintesi vocale dell'annuncio speaker in sidechain mixing con ducking del volume musicale, e visualizzazione overlay animata della richiesta.
- **Messaggi Vocali degli Utenti**: Integrazione bot Telegram/Discord o form web per consentire agli utenti di inviare file audio. Una volta approvati dall'amministratore, vengono normalizzati e mandati in onda.
- **Chat AI "Personaggi" Speaker**: Possibilità per gli utenti di taggare gli speaker (es. `@giulia`, `@marco`) in chat. L'agente risponde elaborando la risposta in tempo reale e sintetizzandola **in onda con la propria voce clonata**.

### 2. Sistema Memoria / Continuità Narrativa (Priorità 2)
- **Memory Engine**: Inserimento di riferimenti temporali incrociati tra i vari blocchi orari (es. alle 14: *"Ne parleremo stasera alle 20..."*; alle 20: *"Come vi avevamo anticipato oggi pomeriggio..."*) per creare continuità narrativa.
- **Storyline Giornaliere**: Programmazione a tema coordinata (es. introduzione tema AI al mattino, approfondimento a pranzo, dibattito la sera, riepilogo la notte) per dare la sensazione di un canale organico.

### 3. Scheduler Dichiarativo (Priorità 3)
- Evoluzione del sistema di scheduling in una struttura dichiarativa robusta per supportare palinsesti complessi, variazioni stagionali, ed eventi speciali con una configurazione centralizzata ed estensibile.

### 4. Dashboard Operativa Avanzata (Priorità 4)
- Creazione di una cabina di regia professionale dotata di:
  - Timeline interattiva del palinsesto.
  - Stato e log degli agenti in tempo reale.
  - Coda audio in riproduzione.
  - Waveform audio live e latenza.
  - Pulsanti di emergenza e override manuale della regia.

### 5. Evoluzione Audiovisiva & Regia Automatica
- **Overlay Dinamici Animati**: Lower thirds animate, cambi palette automatici reattivi alla rubrica, effetti visivi per ultim'ora ed edizioni straordinarie.
- **Camera Virtuale AI**: Regia virtuale con inquadrature dinamiche, zoom lenti, cambi di scena e sorgenti browser animate tramite OBS WebSockets o scene FFmpeg.
- **Waveform & Avatar**: Waveform audio reattive animate sul pannello per dare feedback visivo quando gli speaker (Giulia e Marco) parlano.

### 6. Esperienza Atmosfera & Eventi Speciali
- **Sistema Mood (Atmosfere Dinamiche)**: Il canale cambia veste grafica e sonora in base all'orario (Chill lo-fi con toni scuri la notte, ritmi allegri e colori solari al mattino, drammaticità rossa tesa per edizioni straordinarie).
- **Eventi Live in Automatico**: Modalità copertura speciale per grandi eventi (es. Sanremo, elezioni, eventi tech) con commento live AI, Tweet/Chat reactions in tempo reale e recap costanti.
- **Modalità "Radio Only" & Multi-Output**: Generazione parallela dello stream video per YouTube, stream solo audio Icecast, feed podcast RSS automatico e clip video Short autogenerate.
