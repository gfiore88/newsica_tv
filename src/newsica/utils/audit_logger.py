import os
import json
from datetime import datetime
from pathlib import Path
from newsica.storage.repositories import decision_log_repository

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
RUNTIME_DIR = BASE_DIR / "runtime"


def audit_log_file():
    override = os.getenv("NEWSICA_AUDIT_LOG_FILE")
    if override:
        return Path(override)
    return RUNTIME_DIR / "audit_trail.log"

def log_decision(agent_name: str, decision: str, level: str = "INFO"):
    """
    Registra una decisione di alto livello presa da un agente in un log leggibile.
    Da oggi scrive anche sul database SQLite (decision_logs).
    
    :param agent_name: Il nome dell'agente o del componente (es. "EditorialDirector", "DirectorAgent")
    :param decision: La descrizione della decisione o dell'azione intrapresa
    :param level: Il livello di importanza (es. INFO, WARNING, SCHEDULING, MUSIC)
    """
    # 1. Scrittura su SQLite (nuovo standard)
    decision_log_repository.add(agent_name, level, decision)

    # 2. Scrittura su file legacy (audit_trail.log)
    log_file = audit_log_file()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] [{agent_name}] {decision}\n"
    
    # Stampa anche in console per facilità di debug locale
    print(f"🕵️‍♂️ AUDIT: {log_entry.strip()}")
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
            
        # Manteniamo il file sotto le 500 righe per evitare che esploda
        _rotate_log_if_needed()
    except Exception as e:
        print(f"⚠️ Errore durante la scrittura dell'audit log: {e}")

def _rotate_log_if_needed(max_lines=500):
    try:
        log_file = audit_log_file()
        if not log_file.exists():
            return
            
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if len(lines) > max_lines:
            # Tieni solo le ultime `max_lines`
            lines = lines[-max_lines:]
            with open(log_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
    except Exception:
        pass
