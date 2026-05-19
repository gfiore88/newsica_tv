# Brainstorming — Feature differenzianti per NewsicaTV

Secondo me la feature che può far svoltare davvero NewsicaTV non è “leggere news H24 con voce AI”. Quella rischia di diventare subito uguale a mille canali automatici.

La feature forte dovrebbe essere:

# Regia AI con palinsesto dinamico + breaking news automatiche

Cioè non un semplice loop, ma una vera regia autonoma che decide cosa mandare in onda, quando interrompere, quando fare riepiloghi, quando mettere musica, quando cambiare format e quando generare contenuti speciali.

Questa sarebbe la differenza tra:

> “canale AI che legge RSS”

e

> “web TV automatica con una sua identità editoriale”.

YouTube oggi richiede attenzione ai contenuti sintetici realistici e alla loro disclosure, e nelle policy di monetizzazione penalizza contenuti mass-produced, ripetitivi o inautentici. Quindi la strada vincente non è produrre tanto contenuto generico, ma creare un format riconoscibile, originale e ben orchestrato.

## Le feature che secondo me possono farlo svoltare

## 1. Modalità “Breaking News Interrupt”

Questa per me è la killer feature.

Il canale sta trasmettendo musica o un blocco normale, ma appena il sistema rileva una notizia urgente:

- interrompe il palinsesto
- manda jingle “Ultim’ora”
- cambia grafica
- genera testo breve
- genera audio TTS
- mostra titolo, fonte, categoria e timestamp
- poi torna al programma precedente

Esempio:

```text
[NEWSICATV - ULTIM’ORA]
Interrompiamo la programmazione per un aggiornamento appena arrivato...
```

Tecnicamente potresti avere un `BreakingNewsAgent` che assegna uno score alla notizia:

```text
breaking_score = recency + source_weight + keyword_urgency + duplication_check
```

Se supera una soglia, parte l’interruzione automatica.

Questa feature dà proprio la sensazione di canale vivo.

---

## 2. Palinsesto generato ogni giorno

Ogni mattina il sistema genera un file tipo:

```text
docs/schedules/2026-05-19.md
runtime/schedule/2026-05-19.json
```

Con dentro:

```json
{
  "06:00": "Morning News",
  "07:00": "Italia in 5 minuti",
  "08:00": "Sport Flash",
  "09:00": "Music Rotation",
  "10:00": "Tech & Mondo",
  "13:00": "Pranzo News",
  "18:00": "Riepilogo giornata",
  "21:00": "Newsica Night"
}
```

Questa feature rende il progetto più serio perché non sembra un loop infinito casuale.

In più ogni format può avere tono diverso:

- mattina: veloce, informativo
- pomeriggio: più leggero
- sera: riepilogativo
- notte: musica + flash sintetici

---

## 3. Identità del canale: speaker AI ricorrenti

Non userei una voce anonima unica.

Creerei “personaggi editoriali”, senza imitare persone reali:

```text
Nora — voce principale news
Leo — sport e tecnologia
Mia — musica e cultura pop
Regia — voce neutra per breaking news
```

Così il canale diventa riconoscibile.

Attenzione: eviterei assolutamente cloni vocali di persone reali. Le regole YouTube sui contenuti sintetici realistici richiedono disclosure quando l’AI può far credere che una persona reale abbia detto o fatto qualcosa che non è successo.

---

## 4. Ticker intelligente in basso

Non solo titolo statico.

Un ticker che mostra:

```text
ULTIME: Governo | Sport | Mondo | Meteo | Tecnologia | Prossimo blocco: Newsica Sport alle 18:30
```

Il ticker può avere una sua pipeline autonoma:

```text
NewsCollector -> TickerSummarizer -> ticker.json -> FFmpeg/Overlay
```

Questo aumenta tantissimo la percezione di “canale TV vero”.

---

## 5. Fact-check e anti-allucinazione interno

Questa è meno scenografica, ma fondamentale.

Prima di mandare una news in onda, il sistema dovrebbe fare almeno:

- controllo duplicati
- controllo data
- controllo fonte
- controllo se la notizia è vecchia
- controllo se il testo contiene affermazioni non supportate
- salvataggio fonte originale nel log

Esempio struttura:

```json
{
  "title": "Titolo notizia",
  "category": "Italia",
  "sources": [
    "rss_url_o_link"
  ],
  "confidence": 0.82,
  "aired_at": "2026-05-19T18:30:00",
  "script_file": "content/news/2026-05-19/italia-1830.md",
  "audio_file": "output/audio/italia-1830.wav"
}
```

Questo ti protegge da un problema enorme: un canale AI di news che dice cavolate.

---

## 6. “Riepilogo in 60 secondi” ogni ora

Ogni ora il sistema genera un mini-bollettino:

```text
Sono le 18:00. Ecco le notizie principali dell’ultima ora.
```

Questa è una feature semplice ma fortissima per un canale H24.

Format possibili:

- “Italia in 60 secondi”
- “Mondo in 60 secondi”
- “Sport Flash”
- “Le 5 notizie da sapere”
- “Cosa è successo oggi”

Sono rubriche ripetibili, ma non devono essere identiche nella forma, altrimenti YouTube potrebbe considerarle contenuto ripetitivo/inautentico se troppo mass-produced. La policy monetizzazione parla esplicitamente di contenuti ripetitivi o prodotti in massa come non idonei alla monetizzazione.

---

## 7. Generatore automatico di format

Questa è una feature da “progetto serio”.

Un agente che ogni settimana propone nuovi format e li salva in documentazione:

```text
docs/formats/
  morning-news.md
  sport-flash.md
  notte-ai-music.md
  tech-radar.md
  meteo-e-traffico.md
```

Ogni format dovrebbe avere:

```text
Nome
Durata
Frequenza
Tono
Categorie ammesse
Template grafico
Voce speaker
Musica/jingle
Regole editoriali
```

Esempio:

```text
Format: Newsica Radar
Durata: 7 minuti
Frequenza: ogni 3 ore
Contenuto: 3 news Italia, 2 mondo, 1 sport, 1 tech
Tono: rapido, televisivo, neutro
```

---

## 8. Dashboard locale di controllo

Anche se il canale è automatico, serve una dashboard locale.

Feature utili:

- stato stream: online/offline
- contenuto attualmente in onda
- prossimi contenuti
- ultime news acquisite
- errori TTS
- errori FFmpeg
- uso CPU/GPU/RAM
- spazio disco
- pulsante “forza breaking news”
- pulsante “salta brano”
- pulsante “rigenera scaletta”

Questa è una feature che ti aiuta tantissimo durante lo sviluppo.

---

## 9. Archivio automatico dei contenuti

Ogni contenuto mandato in onda dovrebbe essere archiviato.

Tipo:

```text
archive/
  2026-05-19/
    aired-log.json
    scripts/
    audio/
    video-segments/
    sources/
```

Così puoi:

- controllare cosa è andato in onda
- riutilizzare segmenti
- creare Shorts automaticamente
- generare report
- fare debug
- dimostrare le fonti usate

---

## 10. Shorts automatici dai momenti migliori

Questa potrebbe diventare una seconda linea di crescita.

Il canale H24 genera contenuti lunghi/live, ma il sistema potrebbe creare ogni giorno:

- 3 Shorts news
- 1 Short sport
- 1 Short “notizia assurda”
- 1 Short musicale

Tutto locale, esportato come file pronto da caricare.

Non partirei da qui, però. Prima renderei solida la diretta.

---

# La mia top 5 per priorità

Io farei così:

## Priorità 1 — Regia AI centrale

Senza questa, il progetto è solo una playlist automatica.

Nome possibile:

```text
DirectorAgent
```

Compiti:

- decide cosa va in onda
- gestisce blocchi news/musica
- interrompe per breaking news
- mantiene il ritmo
- scrive il log editoriale

---

## Priorità 2 — Breaking News Interrupt

È la feature che dà identità e immediatezza.

---

## Priorità 3 — Palinsesto giornaliero automatico

Serve per dare forma al canale.

---

## Priorità 4 — Ticker + grafica dinamica

È quello che fa sembrare NewsicaTV una web TV e non un player audio.

---

## Priorità 5 — Fact-check/log fonti

È quello che ti evita problemi seri.

---

# La feature “svolta” in una frase

Secondo me NewsicaTV deve avere questa promessa:

> Una regia AI locale che costruisce e manda in onda un palinsesto H24, alternando news verificate, breaking news automatiche, rubriche e musica AI, con grafica dinamica e archivio completo di tutto ciò che viene trasmesso.

Questa è la direzione giusta.

## Primo documento che creerei ora

Nel progetto io aggiungerei subito:

```text
docs/brainstorming/2026-05-19_feature_svolta_newsicatv.md
```

Con titolo:

```markdown
# Brainstorming — Feature differenzianti per NewsicaTV
```

E dentro salverei:

- obiettivo
- rischi YouTube
- feature candidate
- priorità MVP
- decisione proposta: puntare su `DirectorAgent` + `BreakingNewsAgent`

La prima vera implementazione, secondo me, dovrebbe essere questa:

```text
src/agents/director/
src/agents/breaking-news/
src/runtime/scheduler/
src/runtime/on-air-state/
```

Con un file centrale tipo:

```text
runtime/on-air-state.json
```

che dice sempre cosa sta succedendo:

```json
{
  "status": "ON_AIR",
  "current_block": "music",
  "current_title": "AI Chill Newsica Track 04",
  "next_block": "Italia in 60 secondi",
  "breaking_news_available": false,
  "last_update": "2026-05-19T18:42:00"
}
```

Questo file diventa il cuore della regia.
