# ADR 0048: Supporto Richieste Musicali Chat Freeform nel Prompt ACE-Step

- Stato: Accettato
- Data: 2026-05-26

## Contesto

La pipeline Musica AI da chat riconosceva bene solo un set ristretto di temi canonici e tre lingue principali (`italian`, `english`, `spanish`).

Richieste come:
- `brano rock in napoletano`
- `brano k-pop in giapponese`

venivano parzialmente comprese:
- il tema canonico poteva essere riconosciuto solo in alcuni casi;
- il resto della richiesta finiva in un `custom_brief` debole;
- il prompt LLM continuava a trattare lingua e titolo come campi sostanzialmente chiusi.

Questo comportamento era incoerente con l'obiettivo editoriale di usare la richiesta utente come vero vincolo creativo.

## Decisione

La richiesta utente viene ora trattata come vincolo prioritario e trasmessa al prompt musicale in modo esplicito.

Scelte implementative:
- il parser chat preserva più fedelmente il testo della richiesta, rimuovendo solo il lead-in generico (`vorrei ascoltare`, `metti una canzone`, ecc.);
- `custom_brief` resta un campo libero e più capiente;
- il `Music Director` estrae un eventuale `language_hint` anche per lingue o dialetti non canonici;
- il prompt per l'LLM dichiara che genere, mood, lingua, dialetto, cultura musicale e strumenti citati dall'utente sono vincoli prioritari;
- il JSON richiesto all'LLM non forza più `title_language` e `lyrics_language` ai soli valori mainstream;
- la validazione finale accetta tag di lingua non canonici se coerenti tra titolo e lyrics;
- il fallback locale continua a esistere, ma include comunque la richiesta utente nel prompt.

## Conseguenze

Vantaggi:
- richieste freeform come `k-pop in giapponese` o `rock in napoletano` entrano davvero nel prompt;
- il sistema non degrada più automaticamente ogni richiesta fuori catalogo a una semplice preferenza debole;
- il Director può continuare a usare i temi canonici quando disponibili, senza perdere i dettagli creativi richiesti dall'utente.

Limiti:
- il fallback locale dei testi continua a essere ottimizzato soprattutto per `italian`, `english`, `spanish` e `instrumental`;
- quindi il supporto a lingue/dialetti non canonici è forte nel prompt LLM e nella validazione, ma non equivale a garantire qualità uniforme su ogni lingua possibile.

## File coinvolti

- `src/chat_agent.py`
- `src/newsica/agents/editorial_director.py`
- `src/newsica/tests/test_chat_moderation.py`
- `src/newsica/tests/test_editorial_director_music_titles.py`
