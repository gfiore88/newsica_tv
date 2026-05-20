# 0024 - Inserire podcast serale quando avanza tempo

## Contesto

La fascia `Newsica Sera` puo' durare dalle 20:00 alle 22:00, ma il blocco news standard puo' esaurire lo speaker in pochi minuti. Dopo la chiusura il `DirectorAgent` passava correttamente a `music_rotation_until_deadline`, lasciando pero' una lunga sequenza solo musicale.

## Decisione

Durante la fascia `20:00`, se una rubrica `news` e' gia' entrata in `music_rotation_until_deadline` e mancano almeno 20 minuti al blocco successivo, il `DirectorAgent` inserisce una volta sola `Newsica Podcast - Dopo Sera`.

La generazione resta locale e gratuita: usa la pipeline esistente `run_pipeline("podcast", ...)`, Ollama locale, Chatterbox Multilingual e fallback Kokoro. Dopo il podcast la regia torna alla normale rotazione musicale fino alla deadline delle 22:00.

## Conseguenze

- La fascia serale diventa piu' editoriale senza cambiare il palinsesto runtime gia' generato.
- Il podcast extra non si ripete nello stesso slot grazie al flag `evening_podcast_inserted`.
- `director.py` ora rispetta un `next_segment` esplicito sulle azioni `WAIT_OR_GENERATE`, utile per contenuti editoriali inseriti dentro un blocco gia' attivo.
