#!/bin/bash

# 📺 NewsicaTV — Servizi Management Tool
# Gestione unificata di avvio, arresto, riavvio e stato di tutto l'ecosistema NewsicaTV.

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="$BASE_DIR/runtime"
TMP_DIR="$BASE_DIR/tmp"
VENV_PYTHON="$BASE_DIR/venv/bin/python3"

if [ -f "$BASE_DIR/.env" ]; then
  set -a
  . "$BASE_DIR/.env"
  set +a
fi

# Colori per output premium
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0;37m'
BOLD='\033[1m'

# Assicura la presenza delle cartelle
mkdir -p "$RUNTIME_DIR" "$TMP_DIR"

function get_ace_step_python() {
  local candidates=(
    "$BASE_DIR/.venv_ace_step/bin/python3"
    "$BASE_DIR/.venv_ace_step/bin/python"
    "$BASE_DIR/venv/bin/python3"
    "$BASE_DIR/venv/bin/python"
  )

  for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return
    fi
  done

  command -v python3
}

function show_help() {
  echo -e "${BOLD}📺 NewsicaTV — Script di Gestione Unificato${NC}"
  echo -e "Uso: ./manage.sh [comando]"
  echo ""
  echo -e "${BOLD}Comandi disponibili:${NC}"
  echo -e "  ${GREEN}start${NC}             Avvia tutti i servizi"
  echo -e "  ${RED}stop${NC}              Ferma tutti i servizi in esecuzione, ripulisce lock e pipe"
  echo -e "  ${YELLOW}restart${NC}           Ferma e riavvia tutto in modo pulito"
  echo -e "  ${CYAN}status${NC}            Visualizza lo stato attuale e i PID dei vari componenti"
  echo -e "  ${GREEN}worker-start${NC}      Avvia SOLO i worker AI remoti"
  echo -e "  ${RED}worker-stop${NC}       Ferma SOLO i worker AI remoti"
  echo -e "  ${CYAN}live-health${NC}       Verifica log locali, RTMP e stato pubblico YouTube"
  echo -e "  ${BLUE}logs${NC}              Mostra le ultime righe dei log principali"
  echo -e "  ${PURPLE}tts-spike${NC}         Genera/apre il confronto TTS sperimentale"
  echo -e "  ${PURPLE}install-ace-step${NC}  Crea venv e clona il repo di ACE-Step"
  echo ""
}

function get_pid() {
  local pattern="$1"
  pgrep -f "$pattern" | grep -v "$$" | head -n 1
}

function get_all_pids() {
  local pattern="$1"
  pgrep -f "$pattern" | grep -v "$$"
}

function check_status() {
  local label="$1"
  local pattern="$2"
  local pid
  pid=$(get_pid "$pattern")

  if [ -n "$pid" ]; then
    printf "  %-22s [ %b ]  (PID: %s)\n" "$label" "${GREEN}🟢 ATTIVO${NC}" "$pid"
    return 0
  else
    printf "  %-22s [ %b ]\n" "$label" "${RED}🔴 SPENTO${NC}"
    return 1
  fi
}

function do_status() {
  echo -e "\n${BOLD}📊 Stato dei Servizi NewsicaTV:${NC}"
  echo -e "------------------------------------------------"

  check_status "Dashboard (Web)" "src/dashboard.py"
  check_status "Watchdog" "src/watchdog.sh"
  check_status "Regia (Director)" "src/director.py"
  check_status "Stream Script" "src/stream.sh"
  check_status "Stream (FFmpeg)" "ffmpeg.*audio_pipe"

  check_status "Ticker Agent" "src/ticker_agent.py"
  check_status "Overlay Agent" "src/overlay_agent.py"
  check_status "Chime Agent" "src/hourly_chime_agent.py"
  check_status "Preparation Agent" "src/preparation_agent.py"

  check_status "AI Music Worker" "src/newsica/audio/ai_music_worker.py"

  if [ "${NEWSICA_GENERATION_MODE:-local}" = "remote" ] && [ "${NEWSICA_RUN_GENERATION_WORKER:-false}" = "true" ]; then
    check_status "Generation Worker" "src/generation_worker.py"
  fi

  check_status "Breaking News Daemon" "src/breaking_news_agent.py --daemon"
  check_status "Telegram Agent" "src/telegram_agent.py"

  if [ "$(uname)" = "Darwin" ]; then
    check_status "Anti-Sleep" "caffeinate"
  fi

  echo -e "------------------------------------------------\n"
}

function do_stop() {
  local exclude_telegram=false

  if [ "$1" == "--exclude-telegram" ]; then
    exclude_telegram=true
    echo -e "\n${RED}${BOLD}🛑 Spegnimento parziale di NewsicaTV (bot Telegram ESCLUSO)...${NC}"
  else
    echo -e "\n${RED}${BOLD}🛑 Spegnimento di tutto l'ecosistema NewsicaTV...${NC}"
  fi

  if [ "$(uname)" = "Darwin" ]; then
    local caffeinate_pids
    caffeinate_pids=$(get_all_pids "caffeinate")
    if [ -n "$caffeinate_pids" ]; then
      echo "  -> Arresto caffeinate..."
      kill $caffeinate_pids 2>/dev/null || true
    fi
  fi

  local watchdog_pids
  watchdog_pids=$(get_all_pids "src/watchdog.sh")
  if [ -n "$watchdog_pids" ]; then
    echo "  -> Fermo il Watchdog..."
    kill $watchdog_pids 2>/dev/null || true
  fi

  local targets=(
    "src/stream.sh"
    "src/director.py"
    "src/preparation_agent.py"
    "src/dashboard.py"
    "src/ticker_agent.py"
    "src/overlay_agent.py"
    "src/hourly_chime_agent.py"
    "src/breaking_news_agent.py"
    "src/newsica/audio/ai_music_worker.py"
    "src/generation_worker.py"
  )

  if [ "$exclude_telegram" = false ]; then
    targets+=("src/telegram_agent.py")
  fi

  for target in "${targets[@]}"; do
    local pids
    pids=$(get_all_pids "$target")
    if [ -n "$pids" ]; then
      echo "  -> Arresto $target..."
      kill $pids 2>/dev/null || true
    fi
  done

  local ffmpeg_pids
  ffmpeg_pids=$(get_all_pids "ffmpeg")
  if [ -n "$ffmpeg_pids" ]; then
    echo "  -> Chiusura processi FFmpeg..."
    kill $ffmpeg_pids 2>/dev/null || true
  fi

  sleep 1.5

  for target in "${targets[@]}" "src/watchdog.sh" "ffmpeg"; do
    local pids
    pids=$(get_all_pids "$target")
    if [ -n "$pids" ]; then
      echo -e "  -> ${YELLOW}Forzatura arresto (SIGKILL) per $target...${NC}"
      kill -9 $pids 2>/dev/null || true
    fi
  done

  local screens=(
    "newsica-dashboard"
    "newsica-watchdog"
    "newsica-ai-music-worker"
    "newsica-generation-worker"
    "newsica-bn-daemon"
    "newsica-caffeinate"
  )

  if [ "$exclude_telegram" = false ]; then
    screens+=("newsica-telegram")
  fi

  for session_name in "${screens[@]}"; do
    screen -S "$session_name" -X quit 2>/dev/null || true
  done

  # Pulizia anche di eventuali vecchie sessioni residue create da versioni precedenti.
  local legacy_screens=(
    "newsica-stream"
    "newsica-preparation"
    "newsica-ticker"
    "newsica-overlay"
    "newsica-chime"
  )

  for session_name in "${legacy_screens[@]}"; do
    screen -S "$session_name" -X quit 2>/dev/null || true
  done

  screen -wipe >/dev/null 2>&1 || true

  echo -e "🧹 Rimozione lock e pipe orfane..."

  if [ "$exclude_telegram" = false ]; then
    rm -f "$RUNTIME_DIR"/*.lock 2>/dev/null || true
  else
    find "$RUNTIME_DIR" -name "*.lock" ! -name "telegram_agent.lock" -delete 2>/dev/null || true
  fi

  rm -rf "$RUNTIME_DIR/stream.lock" 2>/dev/null || true

  rm -f "$TMP_DIR/ai_music.lock" 2>/dev/null || true
  rm -f "$TMP_DIR/ai_music_worker.lock" 2>/dev/null || true
  rm -f "$TMP_DIR/audio_pipe" "$TMP_DIR/overlay_pipe" "$TMP_DIR/ffmpeg_progress.txt" 2>/dev/null || true

  echo -e "${GREEN}✅ Spegnimento completato correttamente.${NC}\n"
}

function do_start() {
  echo -e "\n${GREEN}${BOLD}🚀 Avvio dell'ecosistema NewsicaTV...${NC}"

  if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${RED}❌ ERRORE: Ambiente virtuale non trovato in $VENV_PYTHON.${NC}"
    echo -e "Esegui prima: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
  fi

  if [ "$(uname)" = "Darwin" ]; then
    if [ -z "$(get_pid "caffeinate")" ]; then
      echo "  -> Avvio Caffeinate (prevenzione sleep macOS)..."
      screen -dmS newsica-caffeinate caffeinate -dims
      sleep 1
    else
      echo "  [i] Caffeinate già attivo."
    fi
  fi

  echo "  [i] FIFO audio/overlay gestite dal Watchdog."

  if [ -z "$(get_pid "src/dashboard.py")" ]; then
    echo "  -> Avvio Dashboard..."
    screen -dmS newsica-dashboard bash -lc "cd '$BASE_DIR' && exec '$VENV_PYTHON' '$BASE_DIR/src/dashboard.py' > '$TMP_DIR/dashboard.log' 2>&1"
    sleep 2
  else
    echo "  [i] Dashboard già attiva."
  fi

  if [ -z "$(get_pid "src/watchdog.sh")" ]; then
    echo "  -> Avvio Watchdog Regia..."
    screen -dmS newsica-watchdog bash -lc "cd '$BASE_DIR' && exec bash '$BASE_DIR/src/watchdog.sh' > '$TMP_DIR/director.log' 2>&1"
    sleep 2
  else
    echo "  [i] Watchdog Regia già attivo."
  fi

  if [ "${NEWSICA_GENERATION_MODE:-local}" != "remote" ] || [ "${NEWSICA_RUN_GENERATION_WORKER:-false}" = "true" ]; then
    if [ -z "$(get_pid "src/newsica/audio/ai_music_worker.py")" ]; then
      echo "  -> Avvio AI Music Worker..."
      local ace_step_python
      ace_step_python="$(get_ace_step_python)"
      screen -dmS newsica-ai-music-worker bash -lc "cd '$BASE_DIR' && exec '$ace_step_python' -u '$BASE_DIR/src/newsica/audio/ai_music_worker.py' > '$TMP_DIR/ai_music_worker.log' 2>&1"
      sleep 2
    else
      echo "  [i] AI Music Worker già attivo."
    fi
  else
    echo "  [i] AI Music Worker disabilitato in modalità solo-regia."
  fi

  if [ "${NEWSICA_GENERATION_MODE:-local}" = "remote" ] && [ "${NEWSICA_RUN_GENERATION_WORKER:-false}" = "true" ]; then
    if [ -z "$(get_pid "src/generation_worker.py")" ]; then
      echo "  -> Avvio Generation Worker remoto..."
      screen -dmS newsica-generation-worker bash -lc "cd '$BASE_DIR' && exec '$VENV_PYTHON' -u '$BASE_DIR/src/generation_worker.py' > '$TMP_DIR/generation_worker.log' 2>&1"
      sleep 1
    else
      echo "  [i] Generation Worker già attivo."
    fi
  fi

  echo "  [i] Ticker/Overlay/Chime/Preparation gestiti da director.py."
  echo "  [i] Streamer gestito dal Watchdog Regia."

  if [ -z "$(get_pid "src/telegram_agent.py")" ]; then
    echo "  -> Avvio Telegram Bot Agent..."
    screen -dmS newsica-telegram bash -lc "cd '$BASE_DIR' && exec '$VENV_PYTHON' -u '$BASE_DIR/src/telegram_agent.py' > '$TMP_DIR/telegram_agent.log' 2>&1"
    sleep 2
  else
    echo "  [i] Telegram Bot Agent già attivo."
  fi

  if [ -z "$(get_pid "src/breaking_news_agent.py --daemon")" ]; then
    echo "  -> Avvio Breaking News Daemon..."
    screen -dmS newsica-bn-daemon bash -lc "cd '$BASE_DIR' && exec '$VENV_PYTHON' -u '$BASE_DIR/src/breaking_news_agent.py' --daemon > '$TMP_DIR/breaking_news_daemon.log' 2>&1"
    sleep 1
  else
    echo "  [i] Breaking News Daemon già attivo."
  fi

  echo -e "${GREEN}${BOLD}🎉 Avvio completato! ${NC}"
  echo -e "  - Dashboard Web: ${CYAN}http://localhost:5050${NC}"
  echo -e "  - Usa '${BOLD}./manage.sh status${NC}' per verificare lo stato."
  echo ""
}

function do_worker_start() {
  echo -e "\n${GREEN}${BOLD}🚀 Avvio dei Worker AI Remoti...${NC}"

  if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${RED}❌ ERRORE: Ambiente virtuale non trovato in $VENV_PYTHON.${NC}"
    exit 1
  fi

  if [ "$(uname)" = "Darwin" ]; then
    if [ -z "$(get_pid "caffeinate")" ]; then
      echo "  -> Avvio Caffeinate (prevenzione sleep macOS)..."
      screen -dmS newsica-caffeinate caffeinate -dims
      sleep 1
    else
      echo "  [i] Caffeinate già attivo."
    fi
  fi

  if [ -z "$(get_pid "src/newsica/audio/ai_music_worker.py")" ]; then
    echo "  -> Avvio AI Music Worker..."
    local ace_step_python
    ace_step_python="$(get_ace_step_python)"
    screen -dmS newsica-ai-music-worker bash -lc "cd '$BASE_DIR' && exec '$ace_step_python' -u '$BASE_DIR/src/newsica/audio/ai_music_worker.py' > '$TMP_DIR/ai_music_worker.log' 2>&1"
    sleep 2
  else
    echo "  [i] AI Music Worker già attivo."
  fi

  if [ "${NEWSICA_GENERATION_MODE:-local}" = "remote" ] && [ "${NEWSICA_RUN_GENERATION_WORKER:-false}" = "true" ]; then
    if [ -z "$(get_pid "src/generation_worker.py")" ]; then
      echo "  -> Avvio Generation Worker remoto..."
      screen -dmS newsica-generation-worker bash -lc "cd '$BASE_DIR' && exec '$VENV_PYTHON' -u '$BASE_DIR/src/generation_worker.py' > '$TMP_DIR/generation_worker.log' 2>&1"
      sleep 1
    else
      echo "  [i] Generation Worker già attivo."
    fi
  else
    echo "  [!] Attenzione: NEWSICA_GENERATION_MODE non è remote o NEWSICA_RUN_GENERATION_WORKER è false. Il generation_worker NON verrà avviato."
  fi

  echo -e "${GREEN}${BOLD}🎉 Avvio worker completato! ${NC}"
  echo ""
}

function do_worker_stop() {
  echo -e "\n${RED}${BOLD}🛑 Spegnimento dei Worker AI Remoti...${NC}"

  if [ "$(uname)" = "Darwin" ]; then
    local caffeinate_pids
    caffeinate_pids=$(get_all_pids "caffeinate")
    if [ -n "$caffeinate_pids" ]; then
      echo "  -> Arresto caffeinate..."
      kill $caffeinate_pids 2>/dev/null || true
    fi
  fi

  local targets=("src/newsica/audio/ai_music_worker.py" "src/generation_worker.py")

  for target in "${targets[@]}"; do
    local pids
    pids=$(get_all_pids "$target")
    if [ -n "$pids" ]; then
      echo "  -> Arresto $target..."
      kill $pids 2>/dev/null || true
    fi
  done

  local screens=("newsica-ai-music-worker" "newsica-generation-worker" "newsica-caffeinate")

  for session_name in "${screens[@]}"; do
    screen -S "$session_name" -X quit 2>/dev/null || true
  done

  rm -f "$TMP_DIR/ai_music.lock" 2>/dev/null || true
  rm -f "$TMP_DIR/ai_music_worker.lock" 2>/dev/null || true

  echo -e "${GREEN}✅ Spegnimento worker completato.${NC}\n"
}

function do_logs() {
  echo -e "\n${BOLD}📝 Log Recenti Regia/Watchdog (director.log):${NC}"
  echo "------------------------------------------------"
  tail -n 20 "$TMP_DIR/director.log" 2>/dev/null || echo "(Nessun log trovato)"

  echo -e "\n${BOLD}📺 Log Recenti Streamer (stream.log):${NC}"
  echo "------------------------------------------------"
  tail -n 20 "$TMP_DIR/stream.log" 2>/dev/null || echo "(Nessun log trovato)"

  echo -e "\n${BOLD}🎵 Log Recenti AI Music Worker:${NC}"
  echo "------------------------------------------------"
  tail -n 20 "$TMP_DIR/ai_music_worker.log" 2>/dev/null || echo "(Nessun log trovato)"
  echo ""
}

function do_live_health() {
  echo -e "\n${BOLD}🩺 Live Health Check NewsicaTV:${NC}"
  echo -e "------------------------------------------------"

  do_status

  echo -e "${BOLD}Log Regia/Watchdog:${NC}"
  tail -n 40 "$TMP_DIR/director.log" 2>/dev/null || echo "(Nessun director.log trovato)"

  echo -e "\n${BOLD}Log Stream:${NC}"
  tail -n 60 "$TMP_DIR/stream.log" 2>/dev/null || echo "(Nessun stream.log trovato)"

  echo -e "\n${BOLD}Progress FFmpeg:${NC}"
  if [ -s "$TMP_DIR/ffmpeg_progress.txt" ]; then
    tail -n 18 "$TMP_DIR/ffmpeg_progress.txt"
  else
    echo "❌ Nessun progress FFmpeg scritto."
  fi

  echo -e "\n${BOLD}Log AI Music Worker:${NC}"
  tail -n 20 "$TMP_DIR/ai_music_worker.log" 2>/dev/null || echo "(Nessun ai_music_worker.log trovato)"

  echo -e "\n${BOLD}Stato Runtime:${NC}"
  if [ -f "$RUNTIME_DIR/on-air-state.json" ]; then
    cat "$RUNTIME_DIR/on-air-state.json"
    echo ""
  else
    echo "❌ runtime/on-air-state.json mancante."
  fi

  [ -f "$TMP_DIR/current_program.txt" ] && echo "Current: $(cat "$TMP_DIR/current_program.txt")"
  [ -f "$TMP_DIR/next_program.txt" ] && echo "Next: $(cat "$TMP_DIR/next_program.txt")"

  echo -e "\n${BOLD}Runner:${NC}"
  screen -ls 2>/dev/null || true

  if command -v launchctl >/dev/null 2>&1 && command -v rg >/dev/null 2>&1; then
    if launchctl list | rg 'com\.newsica' >/dev/null 2>&1; then
      echo "❌ Trovati processi launchctl Newsica non governati da manage.sh:"
      launchctl list | rg 'com\.newsica'
    else
      echo "✅ Nessun processo launchctl Newsica rilevato."
    fi
  fi

  echo -e "\n${BOLD}Connessione RTMP locale:${NC}"

  local ffmpeg_pid
  ffmpeg_pid=$(get_pid "ffmpeg.*audio_pipe")

  if [ -n "$ffmpeg_pid" ]; then
    if lsof -Pan -p "$ffmpeg_pid" -iTCP -sTCP:ESTABLISHED 2>/dev/null | grep -E ':1935|:443' >/dev/null; then
      echo "✅ FFmpeg ha una connessione RTMP/RTMPS stabilita."
    else
      echo "❌ FFmpeg è attivo ma non risulta una connessione TCP RTMP/RTMPS stabilita."
    fi
  else
    echo "❌ FFmpeg non risulta attivo."
  fi

  echo ""
}

function do_tts_spike() {
  local spike_python="$BASE_DIR/.venv_tts_spike/bin/python"

  if [ ! -x "$spike_python" ]; then
    echo -e "${RED}❌ Ambiente spike non trovato in .venv_tts_spike.${NC}"
    echo -e "Crea l'ambiente con: uv venv --python /opt/homebrew/bin/python3.12 .venv_tts_spike"
    echo -e "Poi installa: uv pip install --python .venv_tts_spike/bin/python numpy soundfile scipy torch torchaudio pocket-tts git+https://github.com/resemble-ai/chatterbox.git"
    exit 1
  fi

  local giulia_ref="$BASE_DIR/assets/voice_refs/giulia_reference.wav"
  local marco_ref="$BASE_DIR/assets/voice_refs/marco_reference.wav"

  if [ -f "$giulia_ref" ] && [ -f "$marco_ref" ]; then
    SPIKE_KYUTAI_GIULIA_VOICE=lola \
    SPIKE_KYUTAI_MARCO_VOICE=giovanni \
    SPIKE_CHATTERBOX_GIULIA_VOICE="$giulia_ref" \
    SPIKE_CHATTERBOX_MARCO_VOICE="$marco_ref" \
      "$spike_python" "$BASE_DIR/src/tts_spike.py" --engines kyutai,chatterbox,fish-s2 --open
  else
    SPIKE_KYUTAI_GIULIA_VOICE=lola \
    SPIKE_KYUTAI_MARCO_VOICE=giovanni \
      "$spike_python" "$BASE_DIR/src/tts_spike.py" --engines kyutai,chatterbox,fish-s2 --open
  fi
}

function do_install_ace_step() {
  echo -e "\n${PURPLE}${BOLD}📦 Installazione ACE-Step in ambiente separato...${NC}"

  local venv_dir="$BASE_DIR/.venv_ace_step"

  if [ ! -d "$venv_dir" ]; then
    echo "Creazione virtual environment: $venv_dir"
    python3 -m venv "$venv_dir"
  fi

  echo "È necessario clonare ACE-Step e installarne i requisiti manualmente o tramite questo script in futuro."
  echo "Usa: $venv_dir/bin/pip install torch torchaudio pydub ..."
  echo -e "${GREEN}Ambiente pronto in $venv_dir.${NC}\n"
}

case "$1" in
  start)
    do_start
    ;;
  stop)
    do_stop "$2"
    ;;
  restart)
    do_stop "$2"
    echo -e "  -> Attesa rilascio lockfile..."
    sleep 3

    if [ "$2" != "--exclude-telegram" ]; then
      rm -f "$RUNTIME_DIR"/*.lock 2>/dev/null || true
    else
      find "$RUNTIME_DIR" -name "*.lock" ! -name "telegram_agent.lock" -delete 2>/dev/null || true
    fi

    do_start
    ;;
  worker-start)
    do_worker_start
    ;;
  worker-stop)
    do_worker_stop
    ;;
  status)
    do_status
    ;;
  logs)
    do_logs
    ;;
  live-health)
    do_live_health
    ;;
  tts-spike)
    do_tts_spike
    ;;
  install-ace-step)
    do_install_ace_step
    ;;
  *)
    show_help
    ;;
esac