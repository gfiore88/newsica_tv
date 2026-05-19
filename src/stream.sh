#!/bin/bash

# Spostati nella root del progetto indipendentemente da dove viene lanciato lo script
cd "$(dirname "$0")/.."

mkdir -p runtime tmp

LOCK_DIR="runtime/stream.lock"
LOCK_OWNER_BASHPID=""
acquire_stream_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    LOCK_OWNER_BASHPID="$BASHPID"
    return 0
  fi

  existing_pid=""
  if [ -f "$LOCK_DIR/pid" ]; then
    existing_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  fi

  if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "❌ ERRORE: stream.sh è già in esecuzione o il lock è detenuto da un processo vivo (PID $existing_pid). Evito una seconda importazione YouTube."
    exit 1
  fi

  echo "⚠️ Lock stream stale trovato. Lo rimuovo e riprovo..."
  rm -rf "$LOCK_DIR"
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    LOCK_OWNER_BASHPID="$BASHPID"
    return 0
  fi

  echo "❌ ERRORE: impossibile acquisire il lock dello stream. Un'altra istanza potrebbe essere partita nello stesso momento."
  exit 1
}

release_stream_lock() {
  if [ "$BASHPID" != "$LOCK_OWNER_BASHPID" ]; then
    return
  fi

  if [ -f "$LOCK_DIR/pid" ] && [ "$(cat "$LOCK_DIR/pid" 2>/dev/null || true)" = "$$" ]; then
    rm -rf "$LOCK_DIR"
  fi
}

acquire_stream_lock

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
LOGO_FILE="assets/splashscreen.png"
PROGRESS_FILE="tmp/ffmpeg_progress.txt"
PROGRAM_FILE="tmp/current_program.txt"
NEXT_PROGRAM_FILE="tmp/next_program.txt"
ACCENT_NEWS_FILE="tmp/accent_news.txt"
ACCENT_SPORT_FILE="tmp/accent_sport.txt"
ACCENT_METEO_FILE="tmp/accent_meteo.txt"
ACCENT_WELLNESS_FILE="tmp/accent_wellness.txt"
ACCENT_MUSIC_FILE="tmp/accent_music.txt"
ACCENT_BREAKING_FILE="tmp/accent_breaking.txt"
CLOCK_FILE="tmp/clock.txt"
DATE_FILE="tmp/date.txt"
STREAM_TEST_CARD="${STREAM_TEST_CARD:-0}"

if [ ! -f "$PROGRAM_FILE" ]; then
  echo "NEWSICA TV" > "$PROGRAM_FILE"
fi
if [ ! -f "$NEXT_PROGRAM_FILE" ]; then
  echo "A seguire: --" > "$NEXT_PROGRAM_FILE"
fi
if [ ! -f "$CLOCK_FILE" ]; then
  echo "--:--" > "$CLOCK_FILE"
fi
if [ ! -f "$DATE_FILE" ]; then
  echo "--/--/----" > "$DATE_FILE"
fi
for accent_file in "$ACCENT_NEWS_FILE" "$ACCENT_SPORT_FILE" "$ACCENT_METEO_FILE" "$ACCENT_WELLNESS_FILE" "$ACCENT_MUSIC_FILE" "$ACCENT_BREAKING_FILE"; do
  if [ ! -f "$accent_file" ]; then
    : > "$accent_file"
  fi
done

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

if ! "$FFMPEG_CMD" -hide_banner -filters 2>/dev/null | grep -q " drawtext "; then
  echo "❌ ERRORE: FFmpeg non include il filtro drawtext. Installa/usa ffmpeg-full per ticker e overlay testuali."
  exit 1
fi

if [ "$STREAM_TEST_CARD" = "1" ]; then
  VIDEO_INPUT_ARGS=(-f lavfi -i "testsrc2=size=1280x720:rate=30")
  FILTER='[0:v]setsar=1,format=yuv420p[bg]; [bg]drawbox=x=0:y=0:w=iw:h=90:color=black@0.75:t=fill[top]; [top]drawtext=text='"'"'NEWSICA TV TEST - SEGNALE VIDEO ATTIVO'"'"':fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=42:x=30:y=25[outv]'
else
  VIDEO_INPUT_ARGS=(-framerate 30 -loop 1 -i "$LOGO_FILE")
  FILTER='[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x0a1128,setsar=1,format=yuv420p,fps=30[bg]; [bg]drawbox=y=ih-80:color=black@0.7:width=iw:height=80:t=fill[bg_box]; [bg_box]drawtext=textfile='"$TICKER_FILE"':reload=1:fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=40:y=h-60:x=w-mod(t*200\,w+tw):alpha=0.9[ticker]; [ticker]drawbox=x=0:y=ih-80:color=red@1:width=250:height=80:t=fill[ticker_box]; [ticker_box]drawtext=text='"'"'ULTIMORA'"'"':fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=35:x=20:y=h-58[main_v]; [main_v]drawbox=x=30:y=30:w=620:h=92:color=0x0f172af5:t=fill[top_bg]; [top_bg]drawtext=text='"'"'ON AIR'"'"':fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=0xfca5a5:fontsize=14:x=52:y=42[top_label]; [top_label]drawtext=textfile='"$PROGRAM_FILE"':reload=1:fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=24:x=52:y=60:expansion=none[current_program]; [current_program]drawtext=textfile='"$NEXT_PROGRAM_FILE"':reload=1:fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=0xcbd5e1:fontsize=16:x=52:y=94:expansion=none[main_osd]; [main_osd]drawbox=x=iw-200:y=30:w=170:h=92:color=0x0f172af5:t=fill[clock_bg]; [clock_bg]drawbox=x=iw-38:y=30:w=8:h=92:color=0xffffff99:t=fill[clock_accent]; [clock_accent]drawtext=textfile='"$CLOCK_FILE"':reload=1:fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=32:x=w-182:y=44[clock_time]; [clock_time]drawtext=textfile='"$DATE_FILE"':reload=1:fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=0xcbd5e1:fontsize=14:x=w-182:y=84[outv]'
fi

FFMPEG_PID=""
WATCHDOG_PID=""
cleanup() {
  if [ -n "$WATCHDOG_PID" ] && kill -0 "$WATCHDOG_PID" 2>/dev/null; then
    kill "$WATCHDOG_PID" 2>/dev/null || true
    wait "$WATCHDOG_PID" 2>/dev/null || true
  fi
  if [ -n "$FFMPEG_PID" ] && kill -0 "$FFMPEG_PID" 2>/dev/null; then
    kill "$FFMPEG_PID" 2>/dev/null || true
    wait "$FFMPEG_PID" 2>/dev/null || true
  fi
  release_stream_lock
}
trap 'cleanup; exit 0' INT TERM
trap 'cleanup' EXIT

watch_ffmpeg_progress() {
  local ffmpeg_pid="$1"
  local last_time=""
  local same_count=0

  while kill -0 "$ffmpeg_pid" 2>/dev/null; do
    sleep 10

    if [ ! -s "$PROGRESS_FILE" ]; then
      continue
    fi

    current_time=$(awk -F= '/^out_time_ms=/ { value=$2 } END { print value }' "$PROGRESS_FILE")
    if [ -z "$current_time" ]; then
      continue
    fi

    if [ "$current_time" = "$last_time" ]; then
      same_count=$((same_count + 1))
    else
      same_count=0
      last_time="$current_time"
    fi

    if [ "$same_count" -ge 3 ]; then
      echo "⚠️ FFmpeg non avanza da 30 secondi (out_time_ms=$current_time). Forzo riavvio..."
      kill "$ffmpeg_pid" 2>/dev/null || true
      return
    fi
  done
}

while true; do
  echo "🚀 Avvio istanza FFmpeg..."
  : > "$PROGRESS_FILE"
  $FFMPEG_CMD \
    -hide_banner -stats_period 5 \
    -progress "$PROGRESS_FILE" \
    -thread_queue_size 4096 "${VIDEO_INPUT_ARGS[@]}" \
    -thread_queue_size 4096 -re -f s16le -ar 24000 -ac 1 -i "$AUDIO_FILE" \
    -filter_complex "$FILTER" \
    -map "[outv]" -map 1:a \
    -c:v libx264 -preset veryfast -tune stillimage \
    -b:v 3000k -minrate 3000k -maxrate 3000k -bufsize 6000k \
    -x264-params "nal-hrd=cbr:force-cfr=1:filler=1" \
    -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -sc_threshold 0 \
    -c:a aac -b:a 128k -ar 44100 \
    -f flv "$YOUTUBE_STREAM_URL/$YOUTUBE_STREAM_KEY" &

  FFMPEG_PID=$!
  watch_ffmpeg_progress "$FFMPEG_PID" &
  WATCHDOG_PID=$!
  wait "$FFMPEG_PID"
  if [ -n "$WATCHDOG_PID" ] && kill -0 "$WATCHDOG_PID" 2>/dev/null; then
    kill "$WATCHDOG_PID" 2>/dev/null || true
    wait "$WATCHDOG_PID" 2>/dev/null || true
  fi
  FFMPEG_PID=""
  WATCHDOG_PID=""
    
  echo "⚠️ FFmpeg si è disconnesso o ha crashato. Riavvio in 5 secondi..."
  sleep 5
done
