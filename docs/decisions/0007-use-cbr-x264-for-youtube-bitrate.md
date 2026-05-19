# ADR 0007: Bitrate CBR reale per YouTube Live

## Context

YouTube Studio richiede un bitrate minimo consigliato per lo stream live. Con `h264_videotoolbox` e una scena quasi statica, FFmpeg dichiarava `4000k`, ma l'encoder hardware emetteva molti meno bit reali perche' l'immagine cambiava poco. YouTube quindi vedeva uno stream intorno a 600-1000 Kbps e segnalava bitrate insufficiente.

## Decision

Lo stream video usa `libx264` in CBR a `3000k`, con `minrate`, `maxrate`, `bufsize` e parametri HRD/filler:

- `-b:v 3000k`
- `-minrate 3000k`
- `-maxrate 3000k`
- `-bufsize 6000k`
- `-x264-params "nal-hrd=cbr:force-cfr=1:filler=1"`

## Consequences

- YouTube riceve un bitrate reale stabile anche quando il video e' statico.
- Il carico CPU aumenta rispetto a `h264_videotoolbox`, ma a 720p30 con preset `veryfast` resta adatto alla regia locale.
- Il bitrate complessivo atteso e' circa 3.1 Mbps includendo audio AAC 128k.
