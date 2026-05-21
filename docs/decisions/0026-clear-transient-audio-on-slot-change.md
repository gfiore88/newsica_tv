# 0026 - Invalidare l'audio temporaneo al cambio fascia

## Contesto

`tmp/audio.wav` e `tmp/audio_part*.wav` sono artefatti temporanei della rubrica appena generata. Dopo un recupero manuale del podcast, il file `tmp/audio.wav` e' rimasto presente e il blocco successivo lo ha considerato audio pronto, rischiando di mandare contenuto podcast dentro lo slot Meteo.

## Decisione

Il `DirectorAgent` invalida gli audio temporanei a ogni inizializzazione di fascia palinsesto:

- `tmp/audio.wav`
- `tmp/is_multipart.txt`
- `tmp/audio_part*.wav`

Inoltre `run_pipeline()` verifica che il TTS produca audio fresco dopo l'avvio della generazione. Se non compare un file audio con mtime successivo all'inizio pipeline, il blocco fallisce invece di riusare audio stale.

## Conseguenze

- Ogni slot deve generare o attendere il proprio audio.
- Un recupero manuale o un podcast immediato non puo' contaminare la fascia successiva.
- I log rendono evidente la sequenza corretta: init fascia, jingle, `WAIT_OR_GENERATE`, TTS fresco, playout.
