# NewsicaTV — DirectorAgent e Trasmissione Straordinaria

## Obiettivo

Introdurre in NewsicaTV un sistema di `DirectorAgent` come regia AI centrale, capace di coordinare palinsesto, rubriche, speaker, musica, jingle, breaking news, ticker e overlay.

Il `DirectorAgent` non deve sostituire il palinsesto, ma deve renderlo più intelligente, fluido e credibile.

La regola principale è:

> Il palinsesto decide cosa va in onda.  
> Il DirectorAgent decide come mandarlo in onda bene.

NewsicaTV deve comportarsi come una vera web TV H24, non come una semplice playlist automatica.

---

## Principio fondamentale: il palinsesto resta sovrano

Il `DirectorAgent` non deve decidere liberamente cosa mandare in onda ignorando gli orari programmati.

Bisogna rispettare gli spettatori: se il palinsesto comunica che alle 14:00 va in onda una determinata rubrica, chi accende la web TV alle 14:00 deve trovare quella rubrica realmente in onda.

Esempio:

```text
14:00 - 14:30 Pausa Wellness
14:30 - 15:00 Music Rotation
15:00 - 15:15 News Update
```

Alle 14:00 il sistema deve entrare in `Pausa Wellness`.

Il `DirectorAgent` non può scegliere arbitrariamente un’altra rubrica.

Può invece decidere, dentro quello slot:

- quale notizia usare;
- quale curiosità aggiungere;
- quale speaker far intervenire;
- quale canzone mettere tra un blocco e l’altro;
- se evitare una notizia già passata poco prima;
- se evitare lo stesso brano troppo ravvicinato;
- se fare un’introduzione breve perché la rubrica è già stata presentata prima;
- se fare un rientro naturale dopo la musica;
- se chiudere in modo ordinato prima della rubrica successiva.

In sintesi:

```text
Palinsesto = cosa deve andare in onda e quando.
DirectorAgent = come quel blocco viene costruito, variato e mandato in onda.
```

Il `DirectorAgent` deve quindi essere:

```text
schedule-aware
schedule-constrained
```

Cioè consapevole del palinsesto e vincolato dal palinsesto.

---

## Regia vincolata agli slot orari

Ogni slot del palinsesto deve essere considerato un contratto con lo spettatore.

Il `DirectorAgent` può lavorare sul contenuto interno dello slot, ma non deve cambiarne la natura.

Esempio:

```text
14:00 - Pausa Wellness
```

Durante quello slot il DirectorAgent può decidere:

- apertura della rubrica;
- argomenti da trattare;
- ordine delle notizie;
- durata dei singoli interventi;
- brani musicali di riempimento coerenti;
- eventuali rientri dopo la musica;
- chiusura prima dello slot successivo;
- contenuti da evitare perché già trasmessi di recente.

Questo permette di avere una web TV prevedibile per lo spettatore, ma non ripetitiva.

---

## Decision Engine vincolato dal palinsesto

Il `Decision Engine` non deve partire da una domanda libera del tipo:

> Cosa mando in onda adesso?

Deve partire da una domanda vincolata:

> Secondo il palinsesto, quale blocco deve essere in onda adesso?  
> Dentro quel blocco, quale contenuto conviene mandare ora?

Input principali:

- orario corrente;
- slot palinsesto attivo;
- tipo di rubrica prevista;
- durata residua dello slot;
- contenuti già trasmessi;
- brani già trasmessi;
- speaker disponibili;
- eventuale breaking news pending;
- stato runtime corrente.

Output esempio:

```json
{
  "scheduled_slot": "14:00-14:30",
  "scheduled_block": "wellness",
  "action": "PLAY_RUBRIC_SEGMENT",
  "segment_type": "curiosity",
  "speaker": "Maya",
  "reason": "Active schedule slot is Pausa Wellness; intro already played; selecting a non-repeated curiosity segment."
}
```

Azioni possibili:

```text
PLAY_JINGLE
PLAY_RUBRIC_SEGMENT
PLAY_MUSIC_FILL
PLAY_BREAKING_NEWS
PLAY_SPECIAL_BROADCAST
RESUME_SCHEDULE
SKIP_TO_CURRENT_SLOT
WRITE_SILENCE_FALLBACK
UPDATE_STATE_ONLY
```

---

## Segmenti interni di una rubrica

Una rubrica non deve essere un blocco monolitico che parte sempre con la stessa introduzione e ripete sempre gli stessi contenuti.

Ogni rubrica dovrebbe poter essere divisa in segmenti.

Esempio:

```json
{
  "rubric": "wellness",
  "title": "Pausa Wellness",
  "segments": [
    {
      "type": "intro",
      "speaker": "Maya",
      "duration_target_seconds": 45
    },
    {
      "type": "news_briefing",
      "speaker": "Maya",
      "duration_target_seconds": 90
    },
    {
      "type": "music_fill",
      "duration_target_seconds": 180
    },
    {
      "type": "curiosity",
      "speaker": "Maya",
      "duration_target_seconds": 75
    },
    {
      "type": "music_fill",
      "duration_target_seconds": 180
    },
    {
      "type": "closing_or_handoff",
      "speaker": "Maya",
      "duration_target_seconds": 40
    }
  ]
}
```

Esempio di flusso desiderato:

```text
jingle
intro rubrica
primo intervento speaker
brano musicale
secondo intervento speaker con nuovo taglio
curiosità / consiglio / aggiornamento
brano musicale
chiusura o passaggio alla prossima fascia
```

---

## Anti-ripetizione

Il `DirectorAgent` deve introdurre una memoria editoriale minima.

File possibile:

```text
runtime/editorial-memory.json
```

Esempio:

```json
{
  "recent_titles": [
    "Allenarsi meglio senza esagerare",
    "Tre consigli per dormire meglio"
  ],
  "recent_rubrics": [
    "wellness",
    "news",
    "music"
  ],
  "recent_music_tracks": [
    "track_04.mp3",
    "track_09.mp3"
  ],
  "last_intro_by_rubric": {
    "wellness": "2026-05-20T11:30:00"
  }
}
```

Questa memoria deve servire a:

- evitare lo stesso brano due volte di seguito;
- evitare lo stesso script;
- evitare la stessa introduzione;
- variare apertura, tono e segmento della rubrica;
- impedire che lo speaker sembri ripetitivo o automatico;
- evitare che vengano riproposte sempre le stesse notizie.

---

## Introduzioni meno ripetitive

Attualmente alcune rubriche rischiano di partire sempre con frasi simili, ad esempio:

```text
Comincia Pausa Wellness, la rubrica di informazione di NewsicaTV.
```

Il `DirectorAgent` dovrebbe fornire al generatore script un contesto più preciso:

```text
Questa è la seconda uscita della rubrica nella stessa fascia.
Non ripetere l’introduzione standard.
Fai un rientro naturale dopo un brano musicale.
Usa tono conversazionale, non da annunciatore.
```

Esempi di rientro:

```text
Torniamo su Pausa Wellness, con un consiglio pratico per affrontare meglio la giornata.
```

```text
Siamo ancora qui su NewsicaTV: dopo la musica, riprendiamo con una curiosità utile sul benessere quotidiano.
```

```text
Rientriamo in studio con Maya per un altro spunto veloce, senza appesantire troppo il ritmo.
```

---

## Valutazione gravità delle news

Il `DirectorAgent` deve rispettare il palinsesto ordinario, ma deve anche essere in grado di gestire eventi eccezionali.

Non tutte le breaking news devono stravolgere il palinsesto.

Serve quindi un sistema di valutazione editoriale delle notizie.

Ogni news valutata dal sistema deve ricevere un punteggio di gravità.

Esempio:

```json
{
  "title": "Forte terremoto in una capitale europea",
  "category": "world",
  "severity_score": 92,
  "confidence_score": 0.87,
  "source_count": 5,
  "is_confirmed": true,
  "recommended_action": "SPECIAL_BROADCAST"
}
```

### Livelli di gravità

```text
0-30   News ordinaria
31-55  News rilevante ma gestibile nel blocco news ordinario
56-75  Breaking news breve
76-89  Breaking news importante con interruzione temporanea
90-100 Trasmissione straordinaria
```

### Regole operative

- Se `severity_score < 56`, la notizia resta nel normale ciclo editoriale.
- Se `severity_score >= 56`, può essere trattata come breaking news.
- Se `severity_score >= 76`, può interrompere temporaneamente il palinsesto.
- Se `severity_score >= 90`, il `DirectorAgent` può proporre o attivare una `TRASMISSIONE_STRAORDINARIA`.

---

## Trasmissione straordinaria

In presenza di notizie di gravità eccezionale, il `DirectorAgent` può attivare una modalità speciale chiamata:

```text
SPECIAL_BROADCAST
```

oppure:

```text
TRASMISSIONE_STRAORDINARIA
```

Questa modalità deve essere usata solo in casi realmente rilevanti.

Esempi:

- eventi gravi di cronaca italiana;
- eventi gravi di cronaca internazionale;
- attentati;
- guerre o escalation militari importanti;
- disastri naturali rilevanti;
- morte di figure istituzionali o pubbliche di enorme rilievo;
- crisi politiche o istituzionali eccezionali;
- eventi mondiali con forte impatto pubblico;
- emergenze nazionali o internazionali.

Non deve essere usata per:

- normali aggiornamenti di cronaca;
- gossip;
- sport ordinario;
- notizie leggere;
- breaking news minori;
- notizie non confermate;
- contenuti ambigui o satirici.

La regola editoriale è:

> Palinsesto sovrano per la normalità.  
> DirectorAgent intelligente dentro lo slot.  
> Trasmissione straordinaria solo per eventi eccezionali, verificati e davvero rilevanti.

---

## Condizioni minime per una trasmissione straordinaria

Una trasmissione straordinaria non deve partire solo perché una singola fonte pubblica una notizia grave.

Devono essere rispettate condizioni minime di affidabilità:

- almeno 2 o 3 fonti autorevoli confermano la notizia;
- la notizia ha rilevanza nazionale o internazionale;
- la notizia è ancora attuale;
- il contenuto non è ambiguo, satirico o non verificato;
- il sistema ha abbastanza informazioni per parlarne senza inventare dettagli;
- il tono della trasmissione può essere gestito in modo sobrio.

Se queste condizioni non sono soddisfatte, il sistema deve usare una formula prudente.

Esempio:

```text
Stiamo seguendo una notizia in evoluzione. Al momento preferiamo attendere ulteriori conferme prima di modificare il palinsesto.
```

---

## Comportamento del DirectorAgent in caso di evento eccezionale

Quando viene rilevata una notizia con gravità eccezionale, il `DirectorAgent` deve:

1. sospendere temporaneamente il palinsesto ordinario;
2. salvare lo slot interrotto;
3. aggiornare lo stato runtime a `SPECIAL_BROADCAST`;
4. attivare eventuale jingle o grafica di edizione straordinaria;
5. generare uno script sobrio e ripetibile per lo speaker;
6. spiegare agli spettatori che il palinsesto è stato modificato;
7. mantenere ticker e overlay coerenti con l’evento;
8. evitare toni sensazionalistici;
9. ripetere periodicamente che si tratta di una trasmissione straordinaria;
10. tornare al palinsesto ordinario quando l’evento non richiede più copertura continua.

Esempio stato runtime:

```json
{
  "status": "SPECIAL_BROADCAST",
  "current_block": "trasmissione_straordinaria",
  "current_title": "Edizione straordinaria",
  "interrupted_slot": "Pausa Wellness",
  "interrupted_slot_start": "14:00",
  "reason": "Evento di cronaca internazionale di eccezionale rilievo",
  "severity_score": 94,
  "is_breaking": true,
  "resume_policy": "RESUME_OR_SKIP_BASED_ON_TIME",
  "last_update": "2026-05-20T14:07:00"
}
```

---

## Linee guida per lo speaker durante una trasmissione straordinaria

Durante una `TRASMISSIONE_STRAORDINARIA`, lo speaker deve comunicare chiaramente agli spettatori che il palinsesto è stato modificato.

Il messaggio deve essere ripetuto più volte, ma senza diventare meccanico.

### Obiettivi dello speaker

Lo speaker deve:

- spiegare che la programmazione ordinaria è stata interrotta;
- chiarire che la scelta è dovuta alla gravità degli eventi;
- mantenere tono sobrio, credibile e rispettoso;
- evitare enfasi teatrale o sensazionalistica;
- distinguere sempre fatti confermati da informazioni in aggiornamento;
- ricordare periodicamente che la trasmissione è straordinaria;
- preparare il ritorno al palinsesto ordinario quando opportuno.

### Esempi di frasi utilizzabili

#### Apertura

```text
Interrompiamo momentaneamente la normale programmazione di NewsicaTV per seguire una notizia di particolare rilevanza che si sta sviluppando in questi minuti.
```

```text
La programmazione prevista per questa fascia viene temporaneamente modificata. Abbiamo scelto di dedicare questo spazio agli ultimi eventi, considerata la loro importanza e il loro possibile impatto.
```

#### Durante la trasmissione

```text
Ricordiamo a chi si è appena collegato che questa è una trasmissione straordinaria di NewsicaTV. Il palinsesto ordinario è stato sospeso temporaneamente per seguire gli aggiornamenti su questa vicenda.
```

```text
Stiamo continuando a seguire questa notizia con prudenza. Alcuni dettagli sono ancora in evoluzione, quindi distingueremo sempre le informazioni confermate da quelle ancora da verificare.
```

#### Rientro dopo musica o pausa

```text
Bentornati su NewsicaTV. Prosegue questa edizione straordinaria: abbiamo modificato il palinsesto previsto per dare spazio agli aggiornamenti sugli eventi delle ultime ore.
```

#### Chiusura

```text
Per il momento chiudiamo questa finestra straordinaria. Continueremo a monitorare gli aggiornamenti e, se necessario, torneremo in onda con nuovi approfondimenti. La programmazione ordinaria di NewsicaTV riprende ora con il palinsesto previsto.
```

---

## Ritorno al palinsesto ordinario

Al termine della trasmissione straordinaria, il `DirectorAgent` deve decidere come rientrare nel palinsesto.

La decisione deve basarsi sull’orario corrente.

Possibili strategie:

```text
RESUME_INTERRUPTED_SLOT
```

Riprende lo slot interrotto, se ha ancora senso e se resta abbastanza tempo.

```text
SKIP_TO_CURRENT_SLOT
```

Salta direttamente al blocco che dovrebbe essere in onda in quel momento.

```text
PLAY_TRANSITION_AND_RESUME
```

Riproduce un breve intervento di raccordo e poi torna al palinsesto.

```text
EXTEND_SPECIAL_BROADCAST
```

Prolunga la trasmissione straordinaria se la notizia è ancora in evoluzione e resta di gravità elevata.

### Regola consigliata

Se lo slot interrotto ha ancora almeno il 40% della durata residua, può essere ripreso.

Se invece lo slot è quasi terminato, il `DirectorAgent` deve passare direttamente allo slot successivo previsto dal palinsesto.

Esempio:

```text
14:00 - 14:30 Pausa Wellness
14:08 - parte trasmissione straordinaria
14:26 - finisce trasmissione straordinaria
```

In questo caso non ha senso riprendere `Pausa Wellness` per soli 4 minuti.

Il `DirectorAgent` deve preparare un raccordo e passare al blocco successivo.

Esempio speaker:

```text
Dopo questa finestra straordinaria, la programmazione di NewsicaTV riprende ora dal punto previsto dal palinsesto. Continueremo naturalmente a seguire la situazione e vi aggiorneremo in caso di ulteriori sviluppi.
```

---

## Stato runtime centrale

Creare o consolidare un file runtime centrale:

```text
runtime/on-air-state/on-air-state.json
```

Esempio:

```json
{
  "status": "ON_AIR",
  "current_block": "wellness",
  "current_title": "Pausa Wellness",
  "current_segment": "speaker_intro",
  "current_speaker": "Maya",
  "next_block": "Music Rotation",
  "is_breaking": false,
  "breaking_news_available": false,
  "last_content_hash": "abc123",
  "started_at": "2026-05-20T12:00:00",
  "last_update": "2026-05-20T12:04:22"
}
```

Questo file deve diventare la fonte unica per:

- ticker;
- overlay;
- dashboard;
- log;
- debug;
- eventuali agenti futuri.

La scrittura deve essere atomica, per evitare file corrotti mentre altri processi lo leggono.

---

## Struttura proposta

Introdurre una struttura modulare:

```text
src/
  agents/
    director/
      __init__.py
      director_agent.py
      decision_engine.py
      runtime_state.py
      schedule_reader.py
      editorial_memory.py
      transition_planner.py

  runtime/
    on-air-state/
      on-air-state.json

  logs/
    editorial/
```

In questa fase si può mantenere compatibilità con l’attuale `src/director.py`.

Il file `director.py` può continuare a essere l’entrypoint principale, ma dovrebbe delegare progressivamente le decisioni al nuovo `DirectorAgent`.

---

## Primo step implementativo consigliato

Non riscrivere tutto subito.

Procedere in modo progressivo.

### Step 1 — Creare il modulo DirectorAgent

Creare:

```text
src/agents/director/director_agent.py
```

Con una classe iniziale:

```python
class DirectorAgent:
    def __init__(self, schedule_reader, runtime_state, editorial_memory):
        self.schedule_reader = schedule_reader
        self.runtime_state = runtime_state
        self.editorial_memory = editorial_memory

    def decide_next_action(self):
        pass

    def update_on_air_state(self, metadata):
        pass

    def notify_interrupt(self, reason):
        pass
```

### Step 2 — Estrarre runtime state

Creare:

```text
src/agents/director/runtime_state.py
```

Responsabilità:

- leggere stato corrente;
- scrivere stato corrente;
- scrittura atomica;
- fallback se il file non esiste;
- evitare crash se JSON corrotto.

### Step 3 — Collegare director.py

Nel file `src/director.py`, mantenere il loop attuale ma delegare la scelta del prossimo blocco a `DirectorAgent`.

Esempio concettuale:

```python
director_agent = DirectorAgent(...)

while True:
    action = director_agent.decide_next_action()
    execute_action(action)
```

In questa prima fase `execute_action` può ancora usare le funzioni già esistenti.

### Step 4 — Log editoriale

Aggiungere log leggibili:

```text
[DirectorAgent] Current slot: 14:00-14:30
[DirectorAgent] Scheduled block: wellness
[DirectorAgent] Next action: PLAY_RUBRIC_SEGMENT
[DirectorAgent] Segment: curiosity
[DirectorAgent] Speaker: Maya
[DirectorAgent] Reason: same schedule slot, music fill completed
```

Questi log devono aiutare a capire perché il sistema ha scelto un contenuto.

---

## Compatibilità con il sistema attuale

Non introdurre regressioni.

Il refactor deve essere progressivo.

Vincoli:

- non rompere `director.py`;
- non rompere la FIFO audio;
- non rompere `ticker_agent.py`;
- non rompere gli overlay FFmpeg;
- non rompere i jingle già integrati;
- non rompere la gestione breaking news attuale;
- non introdurre dipendenze cloud obbligatorie;
- mantenere approccio local-first;
- usare Python standard dove possibile;
- mantenere fallback sicuri.

---

## Criteri di accettazione

La feature è accettabile se:

- il progetto parte ancora con l’entrypoint attuale;
- il `DirectorAgent` viene inizializzato correttamente;
- viene creato/aggiornato `runtime/on-air-state/on-air-state.json`;
- ticker e overlay possono continuare a leggere lo stato;
- il palinsesto viene rispettato negli slot ordinari;
- una rubrica non viene trattata solo come loop ripetitivo;
- il sistema distingue almeno:
  - speaker segment;
  - music fill;
  - jingle;
  - breaking news;
  - trasmissione straordinaria;
  - resume palinsesto;
- una trasmissione straordinaria parte solo per eventi eccezionali e verificati;
- lo speaker comunica chiaramente la variazione del palinsesto;
- dopo una breaking news o trasmissione straordinaria il palinsesto viene ripreso correttamente;
- i log spiegano le decisioni della regia;
- in caso di errore, il sistema continua con fallback sicuro.

---

## Non obiettivi di questa prima fase

Non implementare subito:

- dashboard completa;
- generazione automatica giornaliera del palinsesto;
- fact-check avanzato;
- scoring perfetto delle breaking news;
- multi-speaker realistico completo;
- UI editoriale;
- controllo umano editoriale avanzato.

Questi elementi potranno arrivare dopo.

In questa fase l’obiettivo è creare il cuore architetturale della regia.

---

## Risultato atteso

Al termine di questa implementazione NewsicaTV deve avere un primo vero `DirectorAgent`.

Il sistema non deve limitarsi a eseguire una sequenza, ma deve:

- rispettare il palinsesto;
- costruire bene i contenuti interni agli slot;
- evitare ripetizioni;
- coordinare rubriche, musica, jingle e speaker;
- gestire breaking news;
- attivare trasmissioni straordinarie solo in casi eccezionali;
- comunicare chiaramente agli spettatori eventuali variazioni;
- riprendere correttamente la programmazione ordinaria.

Direzione finale:

> Una regia AI locale che costruisce e manda in onda un palinsesto H24, alternando news verificate, breaking news automatiche, rubriche, musica AI, grafica dinamica e archivio completo di tutto ciò che viene trasmesso.
