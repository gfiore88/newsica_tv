# ADR 0006: Singola importazione YouTube attiva

## Context

YouTube Studio segnala errore quando riceve piu' stream contemporanei sullo stesso URL di importazione principale. Il progetto poteva avviare piu' istanze di `src/stream.sh`, ad esempio da terminale e dalla dashboard, creando piu' processi FFmpeg collegati alla stessa stream key.

## Decision

`src/stream.sh` acquisisce un lock atomico locale in `runtime/stream.lock` prima di leggere la FIFO audio e prima di avviare FFmpeg. Se trova un'altra istanza attiva, esce subito senza avviare una seconda importazione.

La dashboard include anche i processi FFmpeg YouTube nella procedura di restart dello stream, cosi' eventuali processi rimasti orfani vengono terminati prima di rilanciare una singola istanza.

## Consequences

- Non possono partire due stream locali verso la stessa importazione YouTube.
- Il pulsante `Restart Stream` ripulisce sia `stream.sh` sia FFmpeg.
- In caso di crash con lock stale, `stream.sh` rileva il PID non piu' valido, rimuove il lock e riparte.
