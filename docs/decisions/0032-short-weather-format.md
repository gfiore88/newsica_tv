# 0032 - Format meteo breve con rotazione musicale

## Contesto

Lo spazio meteo non deve comportarsi come una rubrica lunga. Per una web TV H24 e' piu' naturale usare il meteo come bollettino breve: aggiornamento nazionale, aree geografiche, temperature e chiusura, poi musica fino allo show successivo.

## Decisione

Il meteo resta una rubrica `single_part`:

- il prompt meteo chiede un solo intervento continuo;
- durata editoriale prevista: circa 3-5 minuti di parlato;
- niente `[MUSIC_BREAK]` e niente parti multiple;
- dopo il bollettino il DirectorAgent passa a uno stacco di uscita e poi a rotazione musicale fino alla deadline dello slot.

## Conseguenze

Una fascia meteo puo' occupare circa 30 minuti di palinsesto, ma solo i primi minuti sono parlati. Il resto e' musica di continuita', evitando copioni meteo lunghi o ripetitivi.
