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

wait_for_pipe() {
  local pipe_path="$1"
  local pipe_label="$2"
  local waited=0

  while [ ! -p "$pipe_path" ]; do
    if [ -e "$pipe_path" ] && [ ! -p "$pipe_path" ]; then
      echo "❌ ERRORE: $pipe_label presente ma non è una FIFO ($pipe_path). Attendo correzione..."
    elif [ $((waited % 5)) -eq 0 ]; then
      echo "⏳ In attesa della FIFO $pipe_label ($pipe_path)..."
    fi

    sleep 1
    waited=$((waited + 1))
  done
}

acquire_stream_lock

# Carica variabili d'ambiente
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

if [ -z "$YOUTUBE_STREAM_KEY" ] || [ "$YOUTUBE_STREAM_KEY" == "inserisci_qui_la_tua_stream_key_di_youtube" ]; then
  echo "❌ ERRORE: Inserisci la tua YOUTUBE_STREAM_KEY nel file .env"
  exit 1
fi

AUDIO_FILE="tmp/audio_pipe"
OVERLAY_PIPE="tmp/overlay_pipe"
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
STREAM_FPS="${STREAM_FPS:-25}"
OVERLAY_FPS="${OVERLAY_FPS:-25}"
STREAM_WIDTH="${STREAM_WIDTH:-1280}"
STREAM_HEIGHT="${STREAM_HEIGHT:-720}"
STREAM_BITRATE="${STREAM_BITRATE:-4500k}"

# Estrae la parte numerica del bitrate per raddoppiarla dinamicamente per il bufsize
BITRATE_NUM=$(echo "$STREAM_BITRATE" | tr -cd '0-9')
STREAM_BUFSIZE="$((BITRATE_NUM * 2))k"

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

echo "🎬 Avvio dello streaming FFmpeg verso YouTube..."
echo "📡 Destinazione: $YOUTUBE_STREAM_URL"

FFMPEG_CMD="/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
if [ ! -f "$FFMPEG_CMD" ]; then
  FFMPEG_CMD="ffmpeg"
fi

STREAM_VIDEO_ENCODER="${STREAM_VIDEO_ENCODER:-auto}"
if [ "$STREAM_VIDEO_ENCODER" = "auto" ]; then
  if "$FFMPEG_CMD" -hide_banner -encoders 2>/dev/null | grep -q "h264_videotoolbox"; then
    STREAM_VIDEO_ENCODER="h264_videotoolbox"
  else
    STREAM_VIDEO_ENCODER="libx264"
  fi
fi

if ! "$FFMPEG_CMD" -hide_banner -filters 2>/dev/null | grep -q " drawtext "; then
  echo "❌ ERRORE: FFmpeg non include il filtro drawtext. Installa/usa ffmpeg-full per ticker e overlay testuali."
  exit 1
fi

if [ "$STREAM_TEST_CARD" = "1" ]; then
  VIDEO_INPUT_ARGS=(-re -f lavfi -i "testsrc2=size=${STREAM_WIDTH}x${STREAM_HEIGHT}:rate=${STREAM_FPS}")
  FILTER='[0:v]setsar=1,format=yuv420p[bg]; [bg]drawbox=x=0:y=0:w=iw:h=90:color=black@0.75:t=fill[top]; [top]drawtext=text='"'"'NEWSICA TV TEST - SEGNALE VIDEO ATTIVO'"'"':fontfile=/System/Library/Fonts/Helvetica.ttc:fontcolor=white:fontsize=42:x=30:y=25[outv]'
else
  # Carichiamo il logo di sfondo a 1 FPS anziché a 25 FPS per risparmiare calcoli di scale/pad pesanti.
  # Rimuoviamo -re per evitare colli di bottiglia nel demuxer di FFmpeg, la velocità è garantita in tempo reale dalle pipe live.
  VIDEO_INPUT_ARGS=(-framerate 1 -loop 1 -i "$LOGO_FILE")

  # Rimuoviamo format=rgba,fps=25 dall'overlay in ingresso: la FIFO e' gia' in RGBA,
  # e il filtro overlay ripete l'ultimo frame automaticamente (repeatlast=1).
  # Una grana molto leggera evita che videotoolbox collassi a bitrate troppo bassi
  # quando la scena e' quasi statica, migliorando l'aggancio di YouTube Live.
  FILTER="[0:v]scale=${STREAM_WIDTH}:${STREAM_HEIGHT}:force_original_aspect_ratio=decrease,pad=${STREAM_WIDTH}:${STREAM_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x0a1128,setsar=1,format=yuv420p,fps=${STREAM_FPS}[bg]; [bg][1:v]overlay=0:0:format=auto,noise=alls=3:allf=t[outv]"
fi

if [ "$STREAM_VIDEO_ENCODER" = "h264_videotoolbox" ]; then
  VIDEO_CODEC_ARGS=(
    -c:v h264_videotoolbox
    -realtime 1
    -allow_sw 1
    -constant_bit_rate true
    -profile:v high
    -b:v "$STREAM_BITRATE"
    -maxrate:v "$STREAM_BITRATE"
    -bufsize:v "$STREAM_BUFSIZE"
    -pix_fmt yuv420p
    -r "$STREAM_FPS"
    -g $((STREAM_FPS * 2))
  )
else
  VIDEO_CODEC_ARGS=(
    -c:v libx264
    -preset veryfast
    -b:v "$STREAM_BITRATE"
    -minrate "$STREAM_BITRATE"
    -maxrate "$STREAM_BITRATE"
    -bufsize "$STREAM_BUFSIZE"
    -x264-params nal-hrd=cbr:force-cfr=1:filler=1
    -pix_fmt yuv420p
    -r "$STREAM_FPS"
    -g $((STREAM_FPS * 2))
    -keyint_min $((STREAM_FPS * 2))
    -sc_threshold 0
  )
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

    local current_time=""
    if [ -s "$PROGRESS_FILE" ]; then
      current_time=$(awk -F= '/^out_time_ms=/ { value=$2 } END { print value }' "$PROGRESS_FILE" 2>/dev/null || true)
    fi

    if [ -z "$current_time" ] || [ "$current_time" = "$last_time" ]; then
      same_count=$((same_count + 1))
    else
      same_count=0
      last_time="$current_time"
    fi

    if [ "$same_count" -ge 9 ]; then
      echo "⚠️ FFmpeg non avanza da 90 secondi (out_time_ms=$current_time). Forzo riavvio..."
      kill "$ffmpeg_pid" 2>/dev/null || true
      return
    fi
  done
}

while true; do
  wait_for_pipe "$AUDIO_FILE" "audio"
  wait_for_pipe "$OVERLAY_PIPE" "overlay"

  echo "🚀 Avvio istanza FFmpeg..."
  echo "🎥 Encoder video selezionato: $STREAM_VIDEO_ENCODER @ ${STREAM_WIDTH}x${STREAM_HEIGHT} stream=${STREAM_FPS}fps overlay=${OVERLAY_FPS}fps"
  : > "$PROGRESS_FILE"
  $FFMPEG_CMD \
    -hide_banner -stats_period 5 \
    -progress "$PROGRESS_FILE" \
    -thread_queue_size 4096 "${VIDEO_INPUT_ARGS[@]}" \
    -thread_queue_size 128 -f rawvideo -pix_fmt rgba -s "${STREAM_WIDTH}x${STREAM_HEIGHT}" -r "$OVERLAY_FPS" -i "$OVERLAY_PIPE" \
    -thread_queue_size 4096 -f s16le -ar 24000 -ac 1 -i "$AUDIO_FILE" \
    -filter_complex "$FILTER" \
    -map "[outv]" -map 2:a \
    "${VIDEO_CODEC_ARGS[@]}" \
    -c:a aac -b:a 128k -ar 48000 -ac 2 \
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
