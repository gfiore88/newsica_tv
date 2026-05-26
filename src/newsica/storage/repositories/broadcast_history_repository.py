import json
import datetime
from newsica.storage.database import get_connection


def add(slot_time: str, block_type: str, title: str, segment: str, event_type: str, asset_path: str, duration_seconds: float = 0.0, metadata_json: dict = None):
    """
    Registra uno storico di messa in onda in maniera 'soft-fail'.
    Se l'inserimento su SQLite fallisce, il processo non si arresta.
    """
    try:
        meta_json_str = json.dumps(metadata_json) if metadata_json else None
        started_at = datetime.datetime.now().isoformat(timespec="seconds")
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO broadcast_history (slot_time, block_type, title, segment, event_type, asset_path, started_at, duration_seconds, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (slot_time, block_type, title, segment, event_type, asset_path, started_at, duration_seconds, meta_json_str))
            conn.commit()
    except Exception as e:
        print(f"⚠️ [SQLite] Errore salvataggio broadcast_history: {e}")
