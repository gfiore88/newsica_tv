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
  
  echo "⚠️ director.py si è fermato o ha crashato. Riavvio in 5 secondi..."
  sleep 5
done
