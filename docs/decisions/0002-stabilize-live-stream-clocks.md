# ADR 0002: Stabilizzazione dei clock audio/video nello streaming live

## Stato
Accettato

## Data
2026-05-18

## Contesto
Lo stream live usa un'immagine statica, ticker dinamico e audio raw PCM tramite named pipe. La pipeline deve restare realtime: se FFmpeg legge la pipe troppo velocemente o se il video non ha un framerate costante esplicito, si possono osservare lentezza, drift o buffering irregolare.

## Decisione
Lo script `src/stream.sh` imposta ora esplicitamente:

- input immagine a 30 fps con `-framerate 30`;
- filtro video a framerate costante con `fps=30`;
- output a 30 fps con GOP da 2 secondi (`-g 60`);
- pacing realtime anche sull'input audio raw con `-re`;
- buffer video coerente per RTMP/YouTube (`-maxrate` e `-bufsize`).

In `src/director.py` i parametri PCM sono centralizzati e il fallback "solo voce" viene convertito a raw PCM tramite FFmpeg, evitando di scrivere header WAV dentro la pipe dichiarata come `s16le`.

## Conseguenze
- Lo stream ha timestamp video piu' prevedibili.
- L'audio raw viene consumato al ritmo dichiarato di 24000 Hz mono.
- I fallback audio mantengono lo stesso formato della pipe.
- La diagnostica FFmpeg e' piu' leggibile grazie a `-hide_banner` e `-stats_period`.
