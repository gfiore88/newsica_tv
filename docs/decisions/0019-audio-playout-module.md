# 0019 - Estrarre audio playout dal director

## Stato

Accettata

## Contesto

`src/director.py` gestiva direttamente coda PCM, processo FFmpeg audio corrente, selezione musica, jingle, sidechain voce/musica, stop dei processi e svuotamento coda. Questa concentrazione rendeva rischioso intervenire su musica, speaker, cambi fascia e breaking news.

## Decisione

La logica audio regolare viene spostata in `src/newsica/audio/`:

- `settings.py`: parametri PCM e risoluzione comando FFmpeg;
- `music_library.py`: selezione tracce da libreria locale e futura libreria AI;
- `jingles.py`: selezione jingle da character registry;
- `playout.py`: coda audio, processo corrente, jingle, musica, sidechain e stop.

`director.py` resta responsabile del runtime: schedule, comandi UI, breaking news, chime e scrittura FIFO. I casi speciali sincroni di chime e breaking news restano temporaneamente nel director per non cambiare troppi comportamenti live nello stesso passaggio.

## Conseguenze

La parte audio regolare e' ora testabile e modificabile senza toccare direttamente il loop principale. La prossima fase puo' estrarre i casi speciali sincroni e introdurre un planner di eventi audio.
