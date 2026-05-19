#!/bin/bash

# 📺 NewsicaTV — Servizi Management Tool
# Gestione unificata di avvio, arresto, riavvio e stato di tutto l'ecosistema NewsicaTV.

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="$BASE_DIR/runtime"
TMP_DIR="$BASE_DIR/tmp"
VENV_PYTHON="$BASE_DIR/venv/bin/python3"

# Colori per output premium
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0;37m' # No Color
BOLD='\033[1m'

# Assicura la presenza delle cartelle
mkdir -p "$RUNTIME_DIR" "$TMP_DIR"

function show_help() {
  echo -e "${BOLD}📺 NewsicaTV — Script di Gestione Unificato${NC}"
  echo -e "Uso: ./manage.sh [comando]"
  echo ""
  echo -e "${BOLD}Comandi disponibili:${NC}"
  echo -e "  ${GREEN}start${NC}     Avvia tutti i servizi (Dashboard, Regia, Stream/FFmpeg)"
  echo -e "  ${RED}stop${NC}      Ferma tutti i servizi in esecuzione, ripulisce lock e pipe"
  echo -e "  ${YELLOW}restart${NC}   Ferma e riavvia tutto in modo pulito"
  echo -e "  ${CYAN}status${NC}    Visualizza lo stato attuale e i PID dei vari componenti"
  echo -e "  ${BLUE}logs${NC}      Mostra le ultime righe dei log principali"
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
  local pid=$(get_pid "$pattern")
  
  if [ -n "$pid" ]; then
    printf "  %-20s [ %b ]  (PID: %s)\n" "$label" "${GREEN}🟢 ATTIVO${NC}" "$pid"
    return 0
  else
    printf "  %-20s [ %b ]\n" "$label" "${RED}🔴 SPENTO${NC}"
    return 1
  fi
}

function do_status() {
  echo -e "\n${BOLD}📊 Stato dei Servizi NewsicaTV:${NC}"
  echo -e "------------------------------------------------"
  check_status "Dashboard (Web)" "src/dashboard.py"
  check_status "Regia (Director)" "src/director.py"
  check_status "Stream (FFmpeg)" "ffmpeg.*audio_pipe"
  check_status "Ticker Agent" "src/ticker_agent.py"
  check_status "Chime Agent" "src/hourly_chime_agent.py"
  check_status "Watchdog" "src/watchdog.sh"
  echo -e "------------------------------------------------\n"
}

function do_stop() {
  echo -e "\n${RED}${BOLD}🛑 Spegnimento di tutto l'ecosistema NewsicaTV...${NC}"
  
  # Termina watchdog prima di tutto
  local watchdog_pids=$(get_all_pids "src/watchdog.sh")
  if [ -n "$watchdog_pids" ]; then
    echo "  -> Fermo il Watchdog..."
    kill -9 $watchdog_pids 2>/dev/null || true
  fi

  # Invia SIGTERM ordinato a Regia, Dashboard e Stream
  local targets=("src/director.py" "src/dashboard.py" "src/stream.sh" "src/ticker_agent.py" "src/hourly_chime_agent.py" "src/breaking_news_agent.py")
  for target in "${targets[@]}"; do
    local pids=$(get_all_pids "$target")
    if [ -n "$pids" ]; then
      echo "  -> Arresto $target..."
      kill $pids 2>/dev/null || true
    fi
  done

  # Termina i processi FFmpeg attivi per Newsica
  local ffmpeg_pids=$(get_all_pids "ffmpeg")
  if [ -n "$ffmpeg_pids" ]; then
    echo "  -> Chiusura processi FFmpeg..."
    kill $ffmpeg_pids 2>/dev/null || true
  fi

  # Attende un attimo e forza il kill se rimangono processi attivi
  sleep 1.5
  for target in "${targets[@]}" "ffmpeg"; do
    local pids=$(get_all_pids "$target")
    if [ -n "$pids" ]; then
      echo -e "  -> ${YELLOW}Forzatura arresto (SIGKILL) per $target...${NC}"
      kill -9 $pids 2>/dev/null || true
    fi
  done

  # Rimozione dei lockfile e della pipe
  echo -e "🧹 Rimozione lock e pipe orfane..."
  rm -f "$RUNTIME_DIR"/*.lock 2>/dev/null || true
  rm -rf "$RUNTIME_DIR"/stream.lock 2>/dev/null || true
  rm -f "$TMP_DIR"/audio_pipe 2>/dev/null || true

  echo -e "${GREEN}✅ Tutto l'ecosistema è stato spento correttamente.${NC}\n"
}

function do_start() {
  echo -e "\n${GREEN}${BOLD}🚀 Avvio dell'ecosistema NewsicaTV...${NC}"
  
  # 1. Verifica ambiente virtuale
  if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${RED}❌ ERRORE: Ambiente virtuale non trovato in $VENV_PYTHON.${NC}"
    echo -e "Esegui prima: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
  fi

  # 2. Crea pipe audio se mancante
  if [ ! -p "$TMP_DIR/audio_pipe" ]; then
    echo "  -> Creazione pipe audio FIFO..."
    mkfifo "$TMP_DIR/audio_pipe"
  fi

  # 3. Avvia la Dashboard (Web Server)
  if [ -z "$(get_pid "src/dashboard.py")" ]; then
    echo "  -> Avvio Dashboard..."
    "$VENV_PYTHON" "$BASE_DIR/src/dashboard.py" > "$TMP_DIR/dashboard.log" 2>&1 &
    sleep 2
  else
    echo "  [i] Dashboard già attiva."
  fi

  # 4. Avvia il Watchdog della Regia (che avvia e monitora director.py)
  if [ -z "$(get_pid "src/watchdog.sh")" ]; then
    echo "  -> Avvio Watchdog Regia..."
    bash "$BASE_DIR/src/watchdog.sh" > "$TMP_DIR/director.log" 2>&1 &
    sleep 2
  else
    echo "  [i] Watchdog Regia già attivo."
  fi

  # 5. Avvia lo Streamer (FFmpeg/YouTube)
  if [ -z "$(get_pid "ffmpeg.*audio_pipe")" ]; then
    echo "  -> Avvio Streamer (FFmpeg)..."
    bash "$BASE_DIR/src/stream.sh" > "$TMP_DIR/stream.log" 2>&1 &
    sleep 1
  else
    echo "  [i] Streamer già attivo."
  fi

  echo -e "${GREEN}${BOLD}🎉 Avvio completato! ${NC}"
  echo -e "  - Dashboard Web: ${CYAN}http://localhost:5050${NC}"
  echo -e "  - Usa '${BOLD}./manage.sh status${NC}' per verificare lo stato."
  echo ""
}

function do_logs() {
  echo -e "\n${BOLD}📝 Log Recenti Regia (director.log):${NC}"
  echo "------------------------------------------------"
  tail -n 12 "$TMP_DIR/director.log" 2>/dev/null || echo "(Nessun log trovato)"
  
  echo -e "\n${BOLD}📺 Log Recenti Streamer (stream.log):${NC}"
  echo "------------------------------------------------"
  tail -n 12 "$TMP_DIR/stream.log" 2>/dev/null || echo "(Nessun log trovato)"
  echo ""
}

case "$1" in
  start)
    do_start
    ;;
  stop)
    do_stop
    ;;
  restart)
    do_stop
    sleep 1
    do_start
    ;;
  status)
    do_status
    ;;
  logs)
    do_logs
    ;;
  *)
    show_help
    ;;
esac
