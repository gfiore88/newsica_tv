# ADR 0034: Flag dashboard per rotazione musica AI

Data: 2026-05-21

## Contesto

NewsicaTV dispone di due sorgenti locali per il filler musicale:

- `assets/music/`: brani inseriti manualmente;
- `assets/ai_music/`: brani generati localmente.

Finora `MusicLibrary` alternava automaticamente le due sorgenti quando entrambe erano disponibili. Serve però un controllo operativo dalla Dashboard per passare a una modalità editoriale "solo Musica AI" senza modificare codice e senza riavviare la diretta.

## Decisione

La modalità musicale viene salvata in `runtime/music-mode.json`.

Sono supportate due modalità:

- `mixed`: usa sia `assets/music/` sia `assets/ai_music/`;
- `ai_only`: usa solo `assets/ai_music/`.

La Dashboard espone un controllo UI e le API `/api/music_mode` in GET/POST. Il playout legge la preferenza a ogni chiamata di selezione brano, quindi il cambio vale dal prossimo brano selezionato.

Il playout applica lo stesso controllo anche quando riceve un file musicale già scelto dal DirectorAgent: in modalità `ai_only`, qualunque path fuori da `assets/ai_music/` viene sostituito con un brano AI valido o rifiutato se la cartella AI è vuota.

## Conseguenze

- Non serve restart del Director per cambiare modalità.
- In `ai_only`, se `assets/ai_music/` è vuota, il sistema non pesca da `assets/music/`: la UI mostra un warning e la regia rispetta la scelta esplicita.
- La logica resta locale e gratuita, senza servizi esterni.
