#!/bin/bash

# Spostati nella root del progetto
# (Uso un percorso relativo calcolato dal file per evitare cd fissi)
# Ma lo script assume di essere in src/

BASE_DIR="$(dirname "$0")/.."

echo "🐕 Watchdog NewsicaTV avviato."
echo "Monitoraggio di director.py..."

while true; do
  echo "🚀 Avvio director.py..."
  "$BASE_DIR/venv/bin/python3" -u "$BASE_DIR/src/director.py"
  exit_code=$?

  if [ "$exit_code" -eq 0 ] || [ "$exit_code" -eq 130 ] || [ "$exit_code" -eq 143 ]; then
    echo "ℹ️ director.py terminato intenzionalmente (exit $exit_code). Riavvio in 5 secondi..."
  else
    echo "⚠️ director.py arrestato in modo anomalo (exit $exit_code). Riavvio in 5 secondi..."
  fi
  sleep 5
done
