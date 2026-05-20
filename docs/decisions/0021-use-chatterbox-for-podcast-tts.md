# ADR 0021: usare Chatterbox Multilingual per i podcast a due voci

## Stato

Accettata.

## Contesto

L'integrazione Qwen3-TTS locale era stata introdotta per ottenere podcast multi-speaker gratuiti e locali. L'audit ha chiarito che l'uso effettivo nel repo era una pipeline a turni: parsing dei tag `[SPEAKER: ...]`, sintesi single-speaker per segmento e concatenazione finale.

Sono stati testati tre candidati locali:

- Fish Audio S2: supporta multi-speaker nativo con token `<|speaker:i|>`, ma su Apple Silicon/MPS ha caricato il modello in circa 65 secondi e ha generato a circa 1 token/s. Non e' pratico per NewsicaTV H24 su questa macchina.
- Kyutai Pocket TTS: molto leggero, ma senza voice cloning abilitato non offre una coppia italiana femminile/maschile adatta a Giulia e Marco.
- Chatterbox Multilingual: non e' un dialogue engine multi-speaker nativo, ma con reference audio reali in `assets/voice_refs/` ha prodotto la resa italiana piu' naturale nella spike.

## Decisione

Per i contenuti `podcast`, NewsicaTV usa Chatterbox Multilingual come provider TTS primario locale.

Le identita' vocali sono definite da:

- `assets/voice_refs/giulia_reference.wav`
- `assets/voice_refs/marco_reference.wav`

Il fallback resta Kokoro, con voci locali gia' disponibili:

- Giulia: `if_sara`
- Marco: `im_nicola`

La pipeline resta a turni: il copione viene parsato tramite `[SPEAKER: Giulia]` e `[SPEAKER: Marco]`, ogni turno viene sintetizzato con il reference corretto, poi i WAV vengono concatenati con micro-pause.

## Conseguenze

- Il sistema resta locale e gratuito, coerente con la regola dell'orchestrator.
- I podcast hanno una resa piu' naturale rispetto alla precedente integrazione Qwen3-TTS Voice Design.
- Chatterbox richiede un ambiente Python 3.12 separato (`.venv_tts_spike`) per evitare incompatibilita' con il runtime principale Python 3.14.
- Qwen3-TTS resta nel repo solo come codice sperimentale/storico finche' non verra' rimosso con un cleanup dedicato.
- Fish Audio S2 non viene integrato nella pipeline H24 su questa macchina.
