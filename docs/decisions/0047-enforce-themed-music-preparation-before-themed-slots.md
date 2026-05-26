# ADR 0047: Preparazione obbligatoria della musica tematica prima degli slot tematici

Data: 2026-05-26

## Contesto

Il palinsesto editoriale puo' assegnare un `theme` agli slot `music_only`, ad esempio:

- `Rock & Roll Arena` con `theme: rock`
- `Newsica Club Fever` con `theme: dance/disco`
- `Baila Newsica` con `theme: latin/reggaeton/dembow`

La runtime sapeva gia':

- leggere il `theme` dal palinsesto;
- generare prompt musicali coerenti con il `theme`;
- filtrare i brani AI per `theme` durante il playout.

Mancava pero' il passaggio decisivo: la pre-produzione anticipata del catalogo musicale tematico in vista dello slot. In assenza di brani taggati con quel tema, la regia degradava silenziosamente a tracce AI generiche, violando il contratto editoriale del titolo in onda.

## Decisione

Gli slot `music_only` con `theme` diventano soggetti a una regola di readiness esplicita:

- il `PreparationAgent` deve accodare in anticipo job `rotation_fill` per quel `theme`;
- la soglia minima di catalogo tematico e' `MUSIC_THEME_MIN_TRACKS` (default `3`);
- il dedupe dei job musica AI non e' piu' globale, ma per tema (`rotation_fill:<theme>`);
- se all'inizio dello slot il catalogo tematico resta sotto soglia, il Director non manda in onda il titolo tematico originale e degrada editorialmente a un titolo musicale generico.

## Conseguenze

- Pro: uno slot tematico non dipende piu' dalla fortuna del catalogo AI gia' presente.
- Pro: la regia inizia a trattare il `theme` come requisito editoriale, non come semplice preferenza soft.
- Pro: la coda musica AI puo' lavorare in anticipo su temi distinti senza confliggere su un solo dedupe globale.
- Pro: in caso di insufficienza catalogo, l'utente non vede un titolo ingannevole come `Rock & Roll Arena` sopra musica non rock.
- Contro: la preparazione musicale tematica puo' aumentare il carico sul worker ACE-Step nelle ore con molte fasce a tema.
- Contro: il fallback editoriale conserva la continuita' della live, ma rinuncia temporaneamente alla promessa tematica se i brani non sono pronti.
