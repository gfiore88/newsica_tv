# NewsicaTV — Regola di Pre-Produzione dei Contenuti

## Obiettivo

NewsicaTV deve garantire continuità editoriale e tecnica dello stream, evitando buchi nel palinsesto causati dai tempi necessari alla generazione dei contenuti AI.

Molti contenuti, come podcast, rubriche strutturate, musica generata con AI o dibattiti a due speaker, richiedono una pipeline composta da più passaggi:

```text
Script LLM
    ↓
Conversione/adattamento dello script con Ollama
    ↓
Passaggio al TTS
    ↓
Eventuale mix audio / jingle / normalizzazione
    ↓
Invio alla regia
```

Questa pipeline richiede tempo e non può essere avviata nel momento esatto della messa in onda.

Il sistema deve quindi separare nettamente:

```text
produzione del contenuto
```

da

```text
messa in onda del contenuto
```

---

## Principio generale

NewsicaTV non deve generare contenuti complessi nel momento esatto in cui devono andare in onda.

Ogni contenuto che richiede una pipeline lunga deve essere preparato anticipatamente rispetto allo slot previsto dal palinsesto, sfruttando i tempi morti della normale programmazione.

La continuità dello stream ha priorità assoluta rispetto alla fedeltà rigida del palinsesto.

Se un contenuto previsto non è pronto entro la deadline editoriale, il DirectorAgent deve attivare un fallback coerente, senza lasciare silenzi, interruzioni o buchi tecnici.

---

## Tipologie di contenuto

### Contenuti rapidi

Sono contenuti brevi, generabili quasi in tempo reale o con tempi molto contenuti.

Esempi:

```text
news flash
meteo breve
ticker
breaking news breve
segnale orario
annuncio palinsesto
intervento speaker breve
```

Questi contenuti possono essere prodottii anche a ridosso della messa in onda, purché non blocchino mai lo stream.

### Contenuti pesanti

Sono contenuti che richiedono una pipeline lunga o più passaggi di generazione.

Esempi:

```text
podcast
rubriche articolate
musica AI generata
interviste simulate
dibattiti a due speaker
speciali editoriali
blocchi con intro, jingle, parlato, musica e outro
```

Questi contenuti devono essere pre-prodotti, validati e accodati prima dello slot previsto.

---

## Nuovo comportamento atteso del DirectorAgent

Il DirectorAgent non deve limitarsi a decidere cosa mandare in onda nel momento corrente.

Deve comportarsi come una combinazione tra:

```text
regista editoriale
production manager
scheduler operativo
supervisore della continuità dello stream
```

Il DirectorAgent deve quindi lavorare su due loop distinti.

---

## On Air Loop

L'`On Air Loop` gestisce ciò che sta andando in onda in quel momento.

Responsabilità principali:

```text
- mandare in onda solo contenuti pronti;
- non lasciare mai buchi audio o video;
- usare musica, jingle, rubriche evergreen o filler se necessario;
- gestire breaking news e variazioni editoriali;
- ripristinare il palinsesto dopo eventuali interruzioni;
- evitare che un contenuto in generazione blocchi lo stream.
```

Regola fondamentale:

```text
La regia può trasmettere solo contenuti in stato ready o queued.
```

---

## Preparation Loop

Il `Preparation Loop` guarda avanti nel palinsesto e prepara in anticipo ciò che servirà dopo.

Responsabilità principali:

```text
- leggere gli slot futuri del palinsesto;
- individuare i contenuti complessi non ancora pronti;
- stimare il tempo necessario per generarli;
- avviare gli agenti corretti durante i tempi morti;
- verificare lo stato di avanzamento degli asset;
- validare che i contenuti siano pronti prima della deadline;
- accodare gli asset pronti per la regia;
- attivare fallback se un contenuto non sarà pronto in tempo.
```

Esempio operativo:

```text
Sono le 09:20.
Alle 10:00 è previsto Newsica Podcast.
Il podcast richiede circa 8-12 minuti di generazione.
Il DirectorAgent avvia subito la pipeline di preparazione.
Alle 09:50 controlla se il file finale è pronto.
Se è pronto, lo mette in coda.
Se non è pronto, attiva un fallback editoriale.
```

---

## Deadline editoriale

Ogni contenuto complesso deve avere una `deadline_ready_at`, cioè un orario entro il quale deve essere pronto.

Esempio:

```json
{
  "slot": "10:00",
  "format": "Newsica Podcast",
  "status": "ready",
  "deadline_ready_at": "09:50",
  "fallback": "music_rotation"
}
```

La deadline non coincide con l'orario di messa in onda.

La deadline deve essere anticipata rispetto allo slot, così da lasciare al sistema il tempo di:

```text
- validare il contenuto;
- accodarlo;
- preparare eventuali jingle;
- calcolare la durata;
- attivare fallback se necessario.
```

---

## Stati dei contenuti

Ogni asset editoriale dovrebbe avere uno stato esplicito.

Stati proposti:

```text
planned     → contenuto previsto dal palinsesto ma non ancora in lavorazione
preparing   → contenuto in fase di generazione
ready       → contenuto generato, validato e disponibile
queued      → contenuto pronto e già accodato per la regia
on_air      → contenuto attualmente in onda
aired       → contenuto già trasmesso
failed      → generazione fallita
expired     → contenuto non più valido editorialmente
```

Regola fondamentale:

```text
Solo i contenuti in stato ready o queued possono essere trasmessi.
```

Un contenuto in stato:

```text
planned
preparing
failed
expired
```

non deve mai bloccare il palinsesto.

---

## Content Buffer / Asset Queue

Il sistema dovrebbe mantenere una coda di contenuti pronti, separando gli asset in lavorazione da quelli disponibili per la messa in onda.

Struttura possibile:

```text
runtime/assets/planned/
runtime/assets/preparing/
runtime/assets/ready/
runtime/assets/queued/
runtime/assets/aired/
runtime/assets/failed/
runtime/assets/archive/
```

Ogni contenuto dovrebbe essere accompagnato da metadata.

Esempio:

```json
{
  "id": "podcast_2026_05_21_1000",
  "type": "podcast",
  "title": "Newsica Podcast delle 10",
  "slot_start": "2026-05-21T10:00:00",
  "duration_target_sec": 900,
  "status": "ready",
  "audio_path": "runtime/assets/ready/podcast_1000.wav",
  "script_path": "runtime/scripts/podcast_1000.md",
  "generated_at": "2026-05-21T09:42:00",
  "deadline_ready_at": "2026-05-21T09:50:00",
  "expires_at": "2026-05-21T12:00:00",
  "fallback_policy": "music_then_news_flash"
}
```

La regia non deve occuparsi di generare il contenuto.

La regia deve solo chiedere:

```text
Esiste un asset pronto e valido per questo slot?
```

Se sì, lo manda in onda.

Se no, attiva il fallback.

---

## Uso dei tempi morti

I tempi morti del palinsesto non devono essere considerati solo momenti da riempire con musica, ma finestre operative da usare per preparare i contenuti successivi.

Esempio:

```text
09:00 - Rubrica News già pronta
09:05 - Musica / filler / playlist locale
09:05-09:25 - mentre va la musica, il sistema prepara il Podcast delle 10
09:25 - controllo qualità audio
09:30 - eventuale generazione secondo blocco
09:45 - asset pronto
10:00 - podcast in onda
```

In questo modo NewsicaTV si comporta come una redazione automatica, non come un sistema che improvvisa tutto all'ultimo secondo.

---

## Responsabilità degli agenti

### Orchestrator

L'Orchestrator deve imporre la regola generale di pre-produzione.

Responsabilità:

```text
- garantire che la continuità dello stream sia prioritaria;
- vietare architetture basate sulla generazione sincrona dei contenuti complessi;
- coordinare DirectorAgent e agenti specializzati;
- assicurarsi che ogni contenuto pesante abbia una deadline editoriale;
- imporre fallback obbligatori per ogni slot complesso;
- impedire che una pipeline AI lenta blocchi la messa in onda.
```

Statement operativo:

```text
Il sistema deve privilegiare sempre la continuità dello stream.
La generazione dei contenuti complessi deve avvenire in anticipo rispetto allo slot previsto.
Nessun agente deve progettare feature che richiedano generazione sincrona all'orario di messa in onda.
```

---

### DirectorAgent

Il DirectorAgent deve guardare avanti nel palinsesto e preparare ciò che servirà dopo.

Responsabilità:

```text
- leggere il palinsesto corrente e futuro;
- guardare almeno N minuti avanti;
- verificare quali asset mancano;
- richiedere la preparazione agli agenti corretti;
- mantenere una coda di contenuti pronti;
- mandare in onda solo asset ready o queued;
- attivare fallback quando un contenuto non è pronto;
- comunicare editorialmente eventuali variazioni;
- ripristinare il palinsesto dopo fallback o breaking news.
```

Il DirectorAgent non deve mai attendere passivamente la fine di una generazione.

Se il contenuto non è pronto in tempo, deve proseguire con il miglior fallback disponibile.

---

### ContentStrategistAgent

Il ContentStrategistAgent deve progettare i contenuti futuri.

Responsabilità:

```text
- definire struttura editoriale dei contenuti;
- preparare topic, scalette e prompt;
- differenziare rubriche e podcast;
- evitare ripetizioni tra gli interventi;
- creare contenuti coerenti con il tema dello slot;
- preparare varianti evergreen utilizzabili come fallback;
- indicare durata target e tono editoriale.
```

Esempi di output:

```text
- scaletta podcast;
- script speaker singolo;
- script dialogato a due speaker;
- intro rubrica;
- blocchi intermedi;
- outro;
- prompt per musica AI;
- fallback evergreen.
```

---

### AIIntegratorAgent

L'AIIntegratorAgent deve gestire la pipeline tecnica di generazione.

Responsabilità:

```text
- gestire passaggi LLM / Ollama / TTS;
- stimare i tempi medi di generazione;
- produrre asset audio completi;
- validare durata, voce, ritmo, formato e volume;
- integrare jingle e sottofondi se previsti;
- esportare asset compatibili con la regia;
- segnalare errori senza bloccare lo stream;
- aggiornare lo stato del contenuto.
```

L'AIIntegratorAgent non deve comunicare direttamente alla regia contenuti incompleti.

Deve consegnare solo asset completi e validati.

---

### SystemAdminAgent

Il SystemAdminAgent deve garantire che la generazione non comprometta la stabilità del sistema.

Responsabilità:

```text
- gestire code, lock e processi concorrenti;
- evitare che più generazioni pesanti partano insieme;
- monitorare CPU, RAM, disco e processi audio;
- pulire asset vecchi o scaduti;
- mantenere directory runtime ordinate;
- evitare corruzione di file in fase di scrittura;
- garantire fallback tecnici in caso di errore.
```

---

## Priorità operative dei task

Il sistema deve poter decidere cosa preparare prima quando le risorse sono limitate.

Priorità proposta:

```text
P0 - Continuità stream, audio filler, silenzio di sicurezza, musica pronta
P1 - Contenuti previsti entro 30 minuti
P2 - Podcast o rubriche previste entro 1-2 ore
P3 - Asset evergreen per archivio e fallback
P4 - Esperimenti, contenuti non urgenti, varianti creative
```

Se il sistema non può generare tutto, deve privilegiare i contenuti più vicini alla messa in onda e la continuità dello stream.

---

## Fallback editoriale

Il fallback non deve essere percepito come errore tecnico.

Deve essere gestito come scelta editoriale coerente.

Esempi:

```text
- rotazione musicale;
- jingle breve;
- rubrica evergreen;
- news flash;
- annuncio palinsesto;
- recupero del contenuto appena disponibile;
- slittamento del contenuto al prossimo slot utile.
```

Esempio per podcast non pronto:

```text
Il podcast previsto non è pronto entro la deadline editoriale.
Il DirectorAgent manda un jingle breve.
Lo speaker comunica che tra poco tornerà Newsica Podcast.
Parte una selezione musicale coerente.
Il sistema continua a monitorare la disponibilità del podcast.
Quando il podcast è pronto, il DirectorAgent decide se recuperarlo, slittarlo o archiviarlo.
```

Frase speaker possibile:

```text
Tra poco torneremo con Newsica Podcast. Nel frattempo restate con noi: spazio alla selezione musicale di NewsicaTV, con aggiornamenti e nuove storie in arrivo nel corso della programmazione.
```

---

## Breaking news

Le breaking news rappresentano un'eccezione controllata.

Una breaking news può modificare il palinsesto solo se supera una soglia editoriale significativa.

In caso di evento grave o molto rilevante:

```text
1. Il DirectorAgent verifica la priorità della breaking news.
2. Se la soglia è alta, interrompe o modifica il palinsesto.
3. Viene mandato un jingle breaking news.
4. Viene generato un blocco breve e rapido.
5. Lo speaker comunica chiaramente la variazione del palinsesto.
6. Al termine, il DirectorAgent decide come recuperare il palinsesto.
```

Frase speaker possibile:

```text
Interrompiamo temporaneamente la normale programmazione di NewsicaTV per seguire una notizia di particolare importanza. Il palinsesto subirà una variazione straordinaria per permetterci di raccontare e aggiornare gli ultimi sviluppi.
```

Dopo la breaking news, il DirectorAgent deve decidere se:

```text
- recuperare il blocco saltato;
- accorciarlo;
- rimandarlo;
- archiviarlo;
- sostituirlo con contenuto più aggiornato.
```

---

## Regola da inserire in orchestrator.md

Sezione proposta:

```md
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
```

---

## Flusso complessivo proposto

```text
Palinsesto futuro
      ↓
DirectorAgent guarda avanti
      ↓
ContentStrategistAgent prepara scaletta e contenuto editoriale
      ↓
AIIntegratorAgent genera script, TTS, audio e asset finale
      ↓
SystemAdminAgent salva asset, gestisce code e aggiorna stato
      ↓
DirectorAgent verifica che l'asset sia ready o queued
      ↓
Regia manda in onda il contenuto
      ↓
Fallback se il contenuto non è pronto
```

---

## Sintesi architetturale

Questa regola trasforma NewsicaTV da un sistema che genera contenuti al momento a una vera redazione automatica.

Il sistema deve sempre sapere:

```text
cosa sta andando in onda ora
cosa andrà in onda dopo
cosa è già pronto
cosa è in preparazione
cosa rischia di non essere pronto
quale fallback usare
```

La generazione AI deve lavorare in anticipo.

La regia deve lavorare solo su asset pronti.

Il DirectorAgent deve essere il punto di raccordo tra produzione, palinsesto e continuità dello stream.
