#!/bin/bash

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

STREAM_SH="$BASE_DIR/src/stream.sh"
DIRECTOR_PY="$BASE_DIR/src/director.py"
TMP_DIR="$BASE_DIR/tmp"
RUNTIME_DIR="$BASE_DIR/runtime"

echo "🐕 Watchdog NewsicaTV avviato."
echo "Monitoraggio coordinato di director.py + stream.sh..."

cleanup_pipeline() {
  echo "🧹 Pulizia pipeline stream/regia..."

  pkill -f "$STREAM_SH" 2>/dev/null || true
  pkill -f "$DIRECTOR_PY" 2>/dev/null || true

  pkill -f "ffmpeg .*tmp/audio_pipe" 2>/dev/null || true
  pkill -f "ffmpeg .*tmp/overlay_pipe" 2>/dev/null || true

  pkill -f "src/overlay_agent.py" 2>/dev/null || true
  pkill -f "src/ticker_agent.py" 2>/dev/null || true
  pkill -f "src/hourly_chime_agent.py" 2>/dev/null || true
  pkill -f "src/preparation_agent.py" 2>/dev/null || true

  rm -rf "$RUNTIME_DIR/stream.lock" 2>/dev/null || true
  rm -f "$TMP_DIR/ffmpeg_progress.txt" 2>/dev/null || true
  rm -f "$TMP_DIR/audio_pipe" "$TMP_DIR/overlay_pipe" 2>/dev/null || true

  mkfifo "$TMP_DIR/audio_pipe"
  mkfifo "$TMP_DIR/overlay_pipe"

  sleep 2
}

is_ffmpeg_rtmp_alive() {
  pgrep -f "ffmpeg .*rtmp://a.rtmp.youtube.com/live2" >/dev/null 2>&1
}

while true; do
  cleanup_pipeline

  echo "🚀 Avvio stream.sh..."
  bash "$STREAM_SH" >> "$TMP_DIR/stream.log" 2>&1 &
  STREAM_PID=$!

  echo "🚀 Avvio director.py..."
  "$BASE_DIR/venv/bin/python3" -u "$DIRECTOR_PY" &
  DIRECTOR_PID=$!

  echo "✅ Pipeline avviata. stream PID=$STREAM_PID, director PID=$DIRECTOR_PID"

  START_TS=$(date +%s)

  while true; do
    sleep 10

    if ! kill -0 "$DIRECTOR_PID" 2>/dev/null; then
      echo "⚠️ director.py terminato. Restart completo pipeline..."
      break
    fi

    if ! kill -0 "$STREAM_PID" 2>/dev/null; then
      echo "⚠️ stream.sh terminato. Restart completo pipeline..."
      break
    fi

    NOW_TS=$(date +%s)
    UPTIME_SEC=$((NOW_TS - START_TS))

    # Lasciamo 30 secondi di grace period per permettere a FFmpeg di agganciare le FIFO e RTMP.
    if [ "$UPTIME_SEC" -gt 30 ] && ! is_ffmpeg_rtmp_alive; then
      echo "⚠️ FFmpeg RTMP non risulta attivo dopo ${UPTIME_SEC}s. Restart completo pipeline..."
      break
    fi
  done

  cleanup_pipeline
  echo "🔁 Riavvio completo tra 5 secondi..."
  sleep 5
done