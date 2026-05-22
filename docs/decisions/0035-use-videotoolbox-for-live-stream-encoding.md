# ADR 0035: usare VideoToolbox come encoder video predefinito per lo stream live su macOS

## Contesto

Il `22 maggio 2026` la diretta YouTube ha mostrato scatti sia audio sia video subito dopo il riavvio locale dei servizi.

I log obbligatori di debug live hanno mostrato:

- `tmp/stream.log`: FFmpeg con `libx264` software restava sotto tempo reale, con `speed` intorno a `0.88x`.
- `tmp/ffmpeg_progress.txt`: avanzamento stabile ma inferiore a realtime (`fps` circa `26.5` su target `30`).
- `tmp/stream.log`: messaggi ripetuti di resume con lag crescente sul ramo video, segnale che il muxer stava inseguendo il tempo di wall clock invece di mantenerlo.
- `ps`: CPU significativa sia su `ffmpeg` sia su `overlay_agent.py`.

Questo indica un collo di bottiglia locale di encoding/compositing, non un problema primario di ingest YouTube.

## Decisione

Su macOS, `src/stream.sh` seleziona ora automaticamente `h264_videotoolbox` quando disponibile, con fallback a `libx264` se l'encoder hardware non esiste o se l'operatore forza esplicitamente `STREAM_VIDEO_ENCODER=libx264`.

Inoltre il target video di default viene abbassato da `30 fps` a `25 fps`, allineando il budget della pipeline al throughput reale osservato con overlay dinamico attivo.

## Conseguenze

- La codifica video live scarica molto piu' lavoro sull'hardware dedicato Apple, lasciando margine a overlay, audio playout e agenti editoriali.
- Il passaggio a `25 fps` riduce il costo totale di compositing/encoding senza cambiare il layout grafico nativo della UI.
- Restano disponibili fallback e override manuale senza cambiare codice.

## Note operative

- Override manuale: `STREAM_VIDEO_ENCODER=libx264 ./manage.sh restart`
- Override framerate: `STREAM_FPS=30 ./manage.sh restart`
- Percorso automatico: `STREAM_VIDEO_ENCODER` non impostata oppure `auto`
- Verifica post-fix: controllare `tmp/stream.log` e `tmp/ffmpeg_progress.txt` cercando `speed >= 1.0x` e assenza di lag crescente.
