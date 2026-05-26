import json
import datetime
from newsica.storage.database import get_connection


def add(agent: str, level: str, message: str, context: dict = None):
    """
    Registra un evento decisionale in maniera 'soft-fail'.
    Se l'inserimento su SQLite fallisce, il processo non si arresta.
    """
    try:
        context_json = json.dumps(context) if context else None
        created_at = datetime.datetime.utcnow().isoformat()
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO decision_logs (agent, level, message, context_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (agent, level, message, context_json, created_at))
            conn.commit()
    except Exception as e:
        print(f"⚠️ [SQLite] Errore salvataggio decision_log ({agent}): {e}")
