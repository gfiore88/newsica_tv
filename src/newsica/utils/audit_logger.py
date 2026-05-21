import os
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
RUNTIME_DIR = BASE_DIR / "runtime"
AUDIT_LOG_FILE = RUNTIME_DIR / "audit_trail.log"

def log_decision(agent_name: str, decision: str, level: str = "INFO"):
    """
    Registra una decisione di alto livello presa da un agente in un log leggibile.
    
    :param agent_name: Il nome dell'agente o del componente (es. "EditorialDirector", "DirectorAgent")
    :param decision: La descrizione della decisione o dell'azione intrapresa
    :param level: Il livello di importanza (es. INFO, WARNING, SCHEDULING, MUSIC)
    """
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] [{agent_name}] {decision}\n"
    
    # Stampa anche in console per facilità di debug locale
    print(f"🕵️‍♂️ AUDIT: {log_entry.strip()}")
    
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
            
        # Manteniamo il file sotto le 500 righe per evitare che esploda
        _rotate_log_if_needed()
    except Exception as e:
        print(f"⚠️ Errore durante la scrittura dell'audit log: {e}")

def _rotate_log_if_needed(max_lines=500):
    try:
        if not AUDIT_LOG_FILE.exists():
            return
            
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if len(lines) > max_lines:
            # Tieni solo le ultime `max_lines`
            lines = lines[-max_lines:]
            with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines)
    except Exception:
        pass
