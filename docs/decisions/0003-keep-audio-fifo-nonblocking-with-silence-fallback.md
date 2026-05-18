# ADR 0003: Fallback a silenzio PCM e watchdog FFmpeg per lo stream H24

## Stato
Accettato

## Data
2026-05-18

## Contesto
La pipeline live si bloccava dopo circa 1-2 minuti: FFmpeg restava vivo e collegato a RTMP, ma il contatore `frame/out_time` non avanzava piu'. La causa operativa era una catena di backpressure tra filler audio live, FIFO e output RTMP.

## Decisione
`src/director.py` non usa piu' un processo FFmpeg di filler live per alimentare la FIFO nei vuoti. Se la coda audio e' vuota, scrive silenzio PCM nel formato dello stream (`s16le`, 24000 Hz, mono). I blocchi editoriali restano mixati con musica quando sono disponibili.

`src/stream.sh` scrive anche un file di progress FFmpeg (`tmp/ffmpeg_progress.txt`) e avvia un watchdog: se `out_time_ms` non avanza per 30 secondi, il processo FFmpeg viene terminato e il loop lo riavvia.

## Conseguenze
- La FIFO riceve sempre dati validi, quindi lo stream non dipende da processi filler che possono bloccarsi.
- In caso di stallo RTMP, il wrapper forza un reconnect invece di lasciare un processo vivo ma fermo.
- Nei momenti in cui la generazione e' ancora in corso e la coda e' vuota, lo stream puo' trasmettere silenzio invece di musica di riempimento.
