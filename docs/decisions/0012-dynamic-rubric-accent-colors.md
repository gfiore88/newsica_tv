# 0012 - Accenti colore per rubrica nell'overlay ON AIR

## Stato

Accettata

## Contesto

L'overlay ON AIR aveva un accento viola fisso. Per rendere piu' riconoscibili le rubriche, serve un colore diverso per ogni tipologia senza dover ricostruire l'intero layout video a ogni cambio fascia.

## Decisione

- La regia scrive file `tmp/accent_*.txt`, uno per ogni tipologia di rubrica.
- Solo il file della rubrica corrente contiene uno spazio; gli altri restano vuoti.
- `stream.sh` disegna piu' box testuali colorati, ciascuno con `reload=1`, e quindi mostra solo l'accento attivo.
- Palette iniziale:
  - news: rosso
  - sport: verde
  - meteo: azzurro
  - wellness: teal
  - musica: viola
  - breaking news: rosso intenso

## Conseguenze

Il colore dell'accento cambia seguendo i metadata della regia e resta compatibile con il flusso overlay basato su file gia' usato per titolo e prossima rubrica. Il filtro FFmpeg deve essere riavviato una volta per passare dalla vecchia barra statica al nuovo sistema dinamico.
