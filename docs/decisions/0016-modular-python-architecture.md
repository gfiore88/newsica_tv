# 0016 - Modularizzare la codebase Python

## Stato

Proposta

## Contesto

Il progetto e' cresciuto rapidamente aggiungendo palinsesto, breaking news, chime, jingle, colori overlay, formati multi-part, dashboard e rotazione fonti. Le responsabilita' principali sono oggi concentrate in `director.py`, `llm_processor.py`, `scraper.py` e `tts_generator.py`.

Questa struttura ha permesso iterazione veloce, ma ora rende costosa ogni estensione: aggiungere una rubrica puo' richiedere modifiche simultanee a prompt, fonti, TTS, regia, jingle e overlay.

## Decisione

Migrare verso una struttura modulare con separazione tra:

- configurazione e paths;
- dominio editoriale: character, rubriche, schedule, contenuti;
- sources: RSS, meteo, rotazione, deduplica;
- editorial: prompt, generazione script, fallback;
- audio: TTS, jingle, musica, mixer, queue;
- broadcast: overlay, stream state, control bus;
- apps: entrypoint compatibili per gli script attuali.

Il refactor deve essere incrementale. Gli entrypoint esistenti in `src/*.py` restano disponibili durante la migrazione.

## Conseguenze

La codebase diventa piu' espandibile e testabile, ma richiede disciplina: ogni fase deve preservare la live e mantenere compatibilita' con gli script attuali. La prima fase deve essere l'estrazione dei character e dei prompt, perche' e' a basso rischio e riduce subito duplicazioni tra LLM, TTS, jingle e overlay.
