# ADR 0008: Rubriche schedulate con riempimento musicale

## Context

La regia generava una rubrica, la mixava con una canzone e poi passava subito a generare di nuovo la stessa rubrica finche' la fascia oraria restava invariata. Inoltre il mix precedente poteva durare quanto l'intera canzone, facendo slittare il cambio rubrica oltre l'orario di palinsesto.

Il comportamento desiderato e' televisivo: una rubrica parte al suo orario, viene introdotta dallo speaker, alterna speaker e brani musicali dentro la stessa fascia, e quando arriva l'orario successivo qualunque contenuto in onda viene interrotto.

## Decision

La regia ora tratta ogni fascia di palinsesto come un blocco:

- genera e manda in onda la parte speaker della fascia;
- aggiunge un'introduzione parlata con il nome della rubrica al copione prima del TTS;
- dopo lo speaker, accoda un singolo brano musicale di riempimento;
- finito il brano, il ciclo puo' tornare allo speaker della stessa rubrica se la fascia non e' cambiata;
- il brano musicale di riempimento evita di ripetere lo stesso file due volte di seguito quando esistono alternative;
- al cambio fascia, imposta un interrupt, termina l'eventuale processo audio in corso e svuota la coda.

## Consequences

- La stessa rubrica puo' ripetersi dentro la propria fascia, intervallata dalla musica.
- La musica resta presente tra un intervento speaker e il successivo.
- Il cambio orario ha priorita' sulla musica e sullo speaker gia' in coda.
