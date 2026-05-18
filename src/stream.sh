#!/bin/bash

# Spostati nella root del progetto indipendentemente da dove viene lanciato lo script
cd "$(dirname "$0")/.."

# Carica variabili d'ambiente
if [ -f .env ]; then
  export $(cat .env | xargs)
fi

if [ -z "$YOUTUBE_STREAM_KEY" ] || [ "$YOUTUBE_STREAM_KEY" == "inserisci_qui_la_tua_stream_key_di_youtube" ]; then
  echo "❌ ERRORE: Inserisci la tua YOUTUBE_STREAM_KEY nel file .env"
  exit 1
fi

AUDIO_FILE="tmp/audio_pipe"
TICKER_FILE="tmp/ticker.txt"
LOGO_FILE="assets/logo.png"

if [ ! -p "$AUDIO_FILE" ]; then
  echo "❌ ERRORE: Pipe audio non trovata ($AUDIO_FILE). Esegui prima director.py"
  exit 1
fi

echo "🎬 Avvio dello streaming FFmpeg verso YouTube..."
echo "📡 Destinazione: $YOUTUBE_STREAM_URL"

# Comando FFmpeg complesso:
# -f lavfi -i color=c=0x0a1128:s=1920x1080:r=30 (crea uno sfondo blu scuro continuo a 1080p)
# -i $AUDIO_FILE (l'audio letto dallo speaker)
# -i $LOGO_FILE (il nostro logo generato)
#
# Filter complex:
# 1. Overlay del logo in alto a destra
# 2. Creazione di un rettangolo nero semitrasparente in basso per il ticker (drawbox)
# 3. Testo scorrevole (drawtext) che legge da ticker.txt. Lo fa scorrere calcolando t e il width.
#
# Poiché l'audio finisce ad un certo punto, -shortest fermerà lo stream, MA in una TV vera dovrebbe loopare.
# Per l'MVP 1 usiamo l'audio per definire la durata dello stream di test.

FFMPEG_CMD="/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
if [ ! -f "$FFMPEG_CMD" ]; then
  FFMPEG_CMD="ffmpeg" # Fallback
fi

FILTER="[0:v][2:v]overlay=W-w-50:50[bg]; [bg]drawbox=y=ih-80:color=black@0.7:width=iw:height=80:t=fill[bg_box]; [bg_box]drawtext=textfile='$TICKER_FILE':reload=1:fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=40:y=h-60:x=w-mod(t*200\,w+tw):alpha=0.9[ticker]; [ticker]drawbox=x=0:y=ih-80:color=red@1:width=250:height=80:t=fill[ticker_box]; [ticker_box]drawtext=text='ULTIMORA':fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=35:x=20:y=h-58[ticker_final]; [ticker_final]drawtext=text='%{localtime\:%H\\\\\:%M\\\\\:%S}':fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=30:x=w-180:y=20:box=1:boxcolor=black@0.6:boxborderw=5[outv]"

$FFMPEG_CMD -re \
  -f lavfi -i "color=c=0x0a1128:s=1920x1080:r=30" \
  -f s16le -ar 24000 -ac 1 -i "$AUDIO_FILE" \
  -i "$LOGO_FILE" \
  -filter_complex "$FILTER" \
  -map "[outv]" -map 1:a \
  -c:v libx264 -preset veryfast \
  -b:v 6000k -minrate 6000k -maxrate 6000k -bufsize 12000k -nal-hrd cbr \
  -pix_fmt yuv420p -g 60 \
  -c:a aac -b:a 128k -ar 44100 \
  -f flv "$YOUTUBE_STREAM_URL/$YOUTUBE_STREAM_KEY"
