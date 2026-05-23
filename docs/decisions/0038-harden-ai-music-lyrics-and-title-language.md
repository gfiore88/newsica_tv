# ADR 0038: Hardening lyrics e lingua del titolo per Musica AI

Data: 2026-05-23

## Contesto

La prima policy multilingua per la musica AI aveva corretto la scelta della lingua target, ma i test runtime hanno mostrato due problemi residui:

- il blocco `Lyrics:` poteva ancora contenere placeholder redazionali o esempi misti invece di testo direttamente cantabile;
- i titoli dei brani potevano restare in inglese anche quando la canzone era richiesta in italiano o in spagnolo.

Per una rotazione H24, questi due scarti degradano la percezione editoriale del catalogo e rendono incoerente il metadata del brano.

## Decisione

Il motore editoriale musicale viene irrigidito su due assi:

1. il prompt musicale rifiuta output con placeholder o note nel blocco `Lyrics:` e richiede lyrics finali, complete e cantabili;
2. il titolo finale del brano non viene più lasciato alla sola risposta LLM, ma viene risolto localmente con un generatore di titoli coerente con `lyrics_language`.

La logica nuova:

- genera fallback lyrics reali in italiano, inglese e spagnolo, senza esempi o testo guida;
- valida il prompt scartando marker come `Example:` o `(Italian lyrics about ...)`;
- assegna un titolo locale di 2 parole nella lingua del brano, evitando collisioni con i titoli recenti.

## Conseguenze

- Pro: maggiore coerenza editoriale tra lingua del brano, titolo e metadata.
- Pro: meno rischio che ACE-Step riceva placeholder invece di lyrics vere.
- Pro: i titoli diventano robusti anche quando Ollama produce un buon prompt ma un titolo in lingua sbagliata.
- Contro: il titolo finale è meno "autoriale" lato LLM perché viene normalizzato localmente.
- Contro: il controllo lingua del titolo è pragmatico e non semantico; privilegia coerenza operativa rispetto a creatività libera.
