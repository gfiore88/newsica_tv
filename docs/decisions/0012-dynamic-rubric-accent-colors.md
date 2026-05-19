# 0012 - Accenti colore per rubrica nell'overlay ON AIR

## Stato

Sospesa

## Contesto

L'overlay ON AIR aveva un accento viola fisso. Per rendere piu' riconoscibili le rubriche, serve un colore diverso per ogni tipologia senza dover ricostruire l'intero layout video a ogni cambio fascia.

## Decisione

- Il tentativo basato su piu' layer `drawtext` ricaricati da `tmp/accent_*.txt` e' sospeso.
- In FFmpeg quei layer hanno introdotto artefatti visivi e un effetto di overlay sovrapposto.
- `stream.sh` mantiene per ora un pannello ON AIR pulito senza accento dinamico.
- Il colore per rubrica verra' reintrodotto nel refactor overlay dedicato, non come patch nel filtro live monolitico.
- Palette iniziale:
  - news: rosso
  - sport: verde
  - meteo: azzurro
  - wellness: teal
  - musica: viola
  - breaking news: rosso intenso

## Conseguenze

La priorita' e' stabilizzare la leggibilita' dell'overlay. Il colore dinamico resta una feature desiderata, ma va implementato con un componente overlay piu' robusto durante il refactor modulare.
