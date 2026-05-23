# ADR 0036: Worker persistente per la musica AI

Data: 2026-05-23

## Contesto

La generazione musicale locale con ACE-Step veniva avviata come script one-shot da `director.py`, dashboard e chat. Ogni job rifaceva l'intera inizializzazione di tokenizer, handler DiT e LLM, con picchi su `MPS` e unified memory proprio durante la diretta.

Nei log questo comportamento appariva come ripetizione continua di:

- `Initializing ACE-Step 1.5 Handlers`
- `loading 5Hz LM tokenizer`
- `5Hz LM initialized successfully using PyTorch backend on mps`

In una diretta H24 questo bootstrap ripetuto compete con `FFmpeg` e aumenta il rischio di stream sotto realtime, backlog e `Broken pipe`.

## Decisione

La generazione musicale AI viene spostata su un worker persistente locale:

- nuovo processo residente `ai_music_worker.py`;
- prewarm iniziale di tokenizer e modelli tramite `get_handlers()`;
- coda locale file-based `runtime/ai_music_jobs.json`;
- `director.py`, dashboard e `chat_agent.py` non eseguono più ACE-Step direttamente, ma accodano job e assicurano che il worker sia attivo;
- deduplica dei job di refill della libreria musicale per evitare tempeste di richieste concorrenti.

Il worker usa un lock dedicato (`tmp/ai_music_worker.lock`) e un log separato (`tmp/ai_music_worker.log`), così `manage.sh` e dashboard possono trattarlo come servizio esplicito.

## Conseguenze

- Pro: tokenizer e modelli restano caldi in RAM tra un brano e l'altro, riducendo il costo di bootstrap ripetuto.
- Pro: il carico GPU/memoria diventa più stabile e prevedibile durante la diretta.
- Pro: dashboard, chat e regia convergono su un'unica pipeline di job locale.
- Pro: i refill automatici della libreria AI vengono serializzati e deduplicati.
- Contro: resta un processo residente aggiuntivo da monitorare.
- Contro: la coda è file-based e non transazionale; per ora è coerente col resto del progetto ma non protegge da race complesse tra molti writer simultanei.
