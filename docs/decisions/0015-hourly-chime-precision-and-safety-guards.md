# ADR 0015: Hourly Chime Precision & Safety Guards

## Contexto & Problema
Durante l'esecuzione automatica H24 di NewsicaTV, è stato riscontrato un conflitto temporale all'inizio delle fasce del palinsesto (es. alle 16:00):
1. Il segnale orario (`hourly_chime_agent.py`) e il cambio fascia (es. da "14:00 - Pomeriggio Sport" a "16:00 - Pausa Wellness") avvengono quasi contemporaneamente.
2. A causa di micro-ritardi di sistema o di sleep, il segnale orario veniva a volte emesso a `15:59:59.999`. Il check originario basato su `now.strftime("%H:00")` calcolava l'ora corrente come `"15:00"`, non rilevando che la chime apparteneva invece all'inizio fascia delle `16:00`.
3. Di conseguenza, la chime veniva trasmessa, forzando un skip sul thread generatore proprio mentre stava avviando la rubrica principale ("Pausa Wellness"). Questo bloccava l'avvio ordinato dello show.
4. Inoltre, gli IDE e i linter di sviluppo generavano avvertimenti su `soundfile` non trovato se eseguiti al di fuori del virtualenv del progetto.

## Decisione Proposta ed Eseguita
Per stabilizzare il comportamento e garantire zero collisioni, abbiamo implementato:

1. **Arrotondamento all'Ora più Vicina (Nearest-Hour Rounding)**:
   - Sia in `director.py` che in `hourly_chime_agent.py`, abbiamo sostituito il controllo semplice del timestamp con un arrotondamento all'ora intera più vicina (tramite aggiunta di 30 minuti e replace a minuto/secondo/microsecondo = 0).
   - In questo modo, qualsiasi evento in un range di ±30 minuti dall'ora in punto (es. `15:59:59` o `16:00:02`) viene mappato in modo solido e coerente alla stringa `"16:00"`.
   - Se l'ora arrotondata coincide con un inizio fascia del palinsesto, la chime viene regolarmente e preventivamente annullata (skip).

2. **Isolamento ed Importazione Dinamica di `soundfile`**:
   - Abbiamo spostato `import soundfile as sf` all'interno della funzione `generate_chime_audio(text)`.
   - Questo previene errori bloccanti di import ed avvertimenti statici da parte degli IDE o linter quando analizzano il file globale al di fuori dell'ambiente virtuale configurato.

## Stato
**Approvato ed Implementato**. I servizi sono stati riavviati con successo e lo stream è attivo.
