import time
import datetime
from newsica.storage.database import get_connection

def insert_memory(memory_type: str, value: str, metadata: str = None):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO editorial_memory (memory_type, value, metadata, created_at)
                VALUES (?, ?, ?, ?)
            ''', (memory_type, value, metadata, now))
            conn.commit()
    except Exception as e:
        print(f"⚠️ Errore db in insert_memory: {e}")

def get_recent_memories(memory_type: str, limit: int = 30):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT value FROM editorial_memory 
                WHERE memory_type = ? 
                ORDER BY id DESC LIMIT ?
            ''', (memory_type, limit))
            # Ritorna la lista dei valori in ordine decrescente (i più recenti per primi)
            return [row['value'] for row in cursor.fetchall()]
    except Exception as e:
        print(f"⚠️ Errore db in get_recent_memories: {e}")
        return []

def get_last_intro_time(rubric: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT created_at FROM editorial_memory 
                WHERE memory_type = 'last_intro' AND metadata = ? 
                ORDER BY id DESC LIMIT 1
            ''', (rubric,))
            row = cursor.fetchone()
            if row:
                return row['created_at']
            return None
    except Exception as e:
        print(f"⚠️ Errore db in get_last_intro_time: {e}")
        return None
