# ADR 0050: validare i copioni podcast prima del TTS

## Contesto

I podcast live di NewsicaTV venivano generati con il path standard di Ollama (`num_predict: 700`) e poi inviati direttamente al TTS. In produzione questo ha prodotto più puntate troncate a metà frase: il testo salvato nel `ready/slot/script.txt` risultava incompleto, il TTS sintetizzava comunque il frammento disponibile e il Director passava subito alla musica dopo il file unico `audio.wav`.

Il problema era aggravato da una divergenza implicita:

- il prompt editoriale chiedeva 450-650 parole e una chiusura naturale;
- la pipeline podcast non supporta `MUSIC_BREAK` interni, ma non lo rendeva esplicito in tutti i punti di generazione;
- non esisteva una validazione locale che bloccasse copioni troppo corti, incompleti o senza chiusura.

## Decisione

Per i contenuti `podcast`:

1. il budget LLM viene aumentato rispetto al path standard;
2. il copione viene validato localmente prima del TTS;
3. se il copione non rispetta il contratto editoriale, Ollama riceve una correzione obbligatoria e rigenera;
4. se i tentativi si esauriscono, il sistema degrada al fallback locale invece di sintetizzare un testo monco;
5. il prompt viene allineato alla realtà del playout: episodio unico continuo, niente `[MUSIC_BREAK]`, chiusura finale con passaggio naturale alla musica.

## Contratto validato

La validazione podcast controlla almeno:

- presenza dei tag speaker;
- numero minimo di turni;
- numero minimo di parole;
- assenza di `[MUSIC_BREAK]`;
- frase finale completa;
- presenza di una chiusura naturale o di un handoff finale alla musica.

## Conseguenze

- Diminuisce il rischio di mandare in onda podcast troncati brutalmente.
- Il comportamento editoriale è coerente con la pipeline reale a file unico.
- In caso di output LLM degradato, il fallback locale resta ascoltabile e chiude correttamente la puntata.
