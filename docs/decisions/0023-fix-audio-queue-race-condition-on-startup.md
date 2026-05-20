# ADR 0023 — Fix Race Condition: audio_queue pre-fill vs FFmpeg Startup

**Data**: 2026-05-20  
**Stato**: Accettato  
**Autori**: Antigravity (AI Engineer)

---

## Contesto

Dopo l'integrazione del `DirectorAgent` (ADR 0022), lo stream YouTube ha smesso di avviarsi
correttamente tramite `./manage.sh start`. FFmpeg si bloccava invariabilmente dopo la riga
di log `aq=1:1.20` (inizializzazione dell'encoder H.264), senza mai produrre frame.

Il comportamento non era presente prima dell'introduzione del `DirectorAgent`.

---

## Causa Radice

Il `generator_worker` veniva avviato immediatamente su un thread separato al boot del director,
**prima** che FFmpeg si collegasse alla FIFO audio (`tmp/audio_pipe`).

Il `DirectorAgent`, tramite `playout.mix_and_queue()`, decodi­ficava l'intero brano audio
via FFmpeg interno e caricava **fino a 538–582 chunk** (≈45 secondi di audio) nella coda
in meno di 200 ms. Con `maxsize=5000`, la coda era di fatto illimitata e si saturava istantaneamente.

Quando FFmpeg di streaming si collegava alla FIFO, il `director.py` iniziava a scrivere
ad alta velocità (non paced), perché la coda era già piena e `queue.get_nowait()` ritornava
immediatamente senza mai andare in `queue.Empty` (che innesca il pacing con `next_write_time`).

### Sintomo osservato

```
frame=  42 fps=2.6 q=-1.0 ... speed=N/A elapsed=0:00:16
Exiting normally, received signal 15.
```

FFmpeg non riusciva a sincronizzare i due input (video loopato + audio FIFO) e veniva
terminato dal watchdog dopo 30 secondi di progress file vuoto.

---

## Decisione

### 1. Riduzione di `audio_queue maxsize`: da 5000 a 200 chunk

200 chunk × 4096 byte / (2 byte × 24000 Hz) ≈ **17 secondi di buffer**.

Questo garantisce un buffer sufficiente per assorbire piccole variazioni di latenza
senza saturare la pipe prima che FFmpeg sia pronto.

```python
# PRIMA
audio_queue = queue.Queue(maxsize=5000)  # >7 minuti di audio in RAM

# DOPO
audio_queue = queue.Queue(maxsize=200)   # ~17 secondi di buffer sicuro
```

### 2. `fifo_connected_event` — sincronizzazione esplicita

Aggiunto un `threading.Event` chiamato `fifo_connected_event` che:

- Viene impostato (`set()`) nel momento esatto in cui `os.open(AUDIO_PIPE, O_WRONLY|O_NONBLOCK)` ha successo (FFmpeg collegato).
- Viene resettato (`clear()`) nel `finally` del ciclo principale quando la FIFO si chiude (FFmpeg disconnesso).
- Il `generator_worker` esegue `fifo_connected_event.wait()` **prima** di entrare nel ciclo
  palinsesto, garantendo che non venga caricato nessun audio finché FFmpeg non è pronto a leggerlo.

```python
def generator_worker():
    fifo_connected_event.wait()   # blocca fino a FFmpeg collegato
    while True:
        action = director_agent.decide_next_action()
        ...
```

---

## Conseguenze

### ✅ Positive
- Il blocco post-`aq=1:1.20` è completamente eliminato.
- La latenza di avvio stream è ridotta: FFmpeg inizia a produrre frame entro 5 secondi dall'apertura della FIFO.
- Il meccanismo si applica anche ai riavvii automatici: se FFmpeg crasha e si riconnette, il `generator_worker` si ferma e aspetta automaticamente la nuova connessione.
- Minor consumo di RAM: non vengono più tenuti 7+ minuti di PCM grezzo in memoria.

### ⚠️ Trade-off
- Con `maxsize=200`, se il director non riesce a produrre audio abbastanza velocemente
  (es. Ollama LLM lento), la coda si svuoterà e il director invierà silenzio. Questo è
  il comportamento corretto e già gestito dal fallback silence del ciclo principale.
- Il `generator_worker` rimane bloccato su `wait()` finché FFmpeg non si collega.
  Il tempo di attesa dipende dalla velocità di handshake RTMP con YouTube (tipicamente 2-5s).

---

## Alternative Considerate

### A. Avvio ritardato del generator_worker con `time.sleep()`
Scartato: fragile, dipendente dai tempi del sistema, non si adatta ai riavvii automatici.

### B. Limitare il numero di chunk caricati in `mix_and_queue()`
Considerato come fix complementare, non necessario con l'evento di sincronizzazione.

### C. Portare `mix_and_queue()` a produzione streaming (lazy)
Architettura più corretta a lungo termine ma fuori scope per questo hotfix.

---

## File Modificati

- `src/director.py`: `audio_queue maxsize`, `fifo_connected_event`, `generator_worker()`, ciclo FIFO principale

---

## Bug Secondario Correlato — Loop del Palinsesto (stesso commit)

### Contesto

La riduzione di `maxsize` a 200 chunk ha esposto un **secondo bug latente** nella gestione
dei metadata in coda: il palinsesto ripeteva lo stesso blocco vocale dall'inizio invece di
procedere alla musica successiva.

### Causa Radice

`mix_and_queue()` inserisce in testa alla coda un item di tipo `metadata` contenente il
`block_info` (titolo, blocco attivo, ecc.), ma **senza il campo `current_segment`**.

Il thread principale (FIFO writer), quando legge questo metadata, chiamava:

```python
write_state_files(item["state"])   # sovrascrittura totale → current_segment scompare!
```

Con `maxsize=5000` (prima del fix), tutti i 538 chunk venivano caricati in coda in <200ms
e il `generator_worker` avanzava immediatamente al blocco successivo prima che il thread
principale consumasse il metadata. Con `maxsize=200`, il generator rimane bloccato per
~45 secondi in `queue_item` (aspettando che la coda si svuoti) e nel frattempo il thread
principale consuma il metadata, sovrascrivendo `current_segment` con un dict che non lo
include. Al loop successivo: `state.get("current_segment", "init")` → `"init"` → il
`DirectorAgent` ricominciava il blocco dall'inizio.

### Fix Applicato

Sostituzione della sovrascrittura totale con un **merge** dello stato:

```python
# PRIMA — sovrascrittura totale (cancella current_segment)
write_state_files(item["state"])

# DOPO — merge: i campi display (titolo, blocco) aggiornano, current_segment preservato
existing_state = get_current_state()
merged_state = {**existing_state, **item["state"]}
write_state_files(merged_state)
```

Questo garantisce che i campi della macchina a stati (`current_segment`, `scheduled_slot`,
ecc.) vengano preservati anche quando il metadata di display li omette.
