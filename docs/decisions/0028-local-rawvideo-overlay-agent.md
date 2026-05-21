# 0028 - Overlay grafico locale via rawvideo FIFO

## Contesto

L'overlay video era costruito quasi interamente dentro `src/stream.sh` con una catena lunga di filtri FFmpeg `drawbox` e `drawtext`. Questo approccio ha reso difficile migliorare la grafica e ha causato tagli sui testi del riquadro dei prossimi eventi, perché FFmpeg non offre un vero motore di layout per pannelli dinamici.

## Decisione

Manteniamo FFmpeg come componente di encoding, muxing e invio RTMP, ma spostiamo la HUD in un processo locale dedicato:

- `src/overlay_agent.py` renderizza un frame RGBA trasparente 1280x720 con Pillow.
- Il frame viene scritto a 1 fps nella FIFO `tmp/overlay_pipe` in formato rawvideo RGBA.
- `src/stream.sh` legge `tmp/overlay_pipe` come secondo input video e lo sovrappone allo sfondo.
- Il ticker scorrevole resta temporaneamente in FFmpeg, perché richiede animazione continua e `drawtext` lo gestisce ancora in modo semplice.

Tutto resta locale e gratuito. Non vengono introdotti browser headless, OBS o servizi cloud.

## Conseguenze

La grafica ON AIR, orologio e prossimi eventi diventa modificabile in Python con layout misurato in pixel, ellissi controllata e colori per tipologia di blocco.

Il costo memoria resta contenuto: un frame RGBA 1280x720 pesa circa 3,5 MB, più l'overhead del processo Python/Pillow. Non viene mantenuto un browser residente.

La pipeline live ora richiede anche `tmp/overlay_pipe` e un processo `overlay_agent.py` attivo. `manage.sh`, `director.py` e la dashboard sono stati aggiornati per includere questo agente.

## Alternative considerate

- **Solo FFmpeg `drawtext`/`drawbox`**: leggero, ma non scalabile per una HUD moderna.
- **PNG aggiornato su file e ricaricato da FFmpeg**: scartato perché il filtro `movie` disponibile localmente non supporta `reload=1` e gli input immagine non ricaricano in modo affidabile il file sostituito.
- **HTML/CSS con browser headless o OBS Browser Source**: più flessibile, ma introduce più RAM, più processi e più punti di failure per un canale H24.
