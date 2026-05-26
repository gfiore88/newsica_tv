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

def add_music_title(title: str):
    insert_memory('music_title', title)

def get_recent_music_titles(limit: int = 30):
    return get_recent_memories('music_title', limit)

def set_memory(memory_type: str, value: str, metadata: str = None):
    insert_memory(memory_type, value, metadata)

def get_memory(memory_type: str):
    memories = get_recent_memories(memory_type, limit=1)
    if memories:
        return memories[0]
    return None

def add_title(title: str):
    insert_memory('title', title)

def add_rubric(rubric: str):
    insert_memory('rubric', rubric)

def add_music_track(track_path: str):
    insert_memory('music_track', track_path)

def is_title_recent(title: str, limit: int = 10) -> bool:
    recent = get_recent_memories('title', limit)
    return title in recent

def is_music_track_recent(track_path: str, limit: int = 10) -> bool:
    recent = get_recent_memories('music_track', limit)
    return track_path in recent

def should_short_intro(rubric: str) -> bool:
    from datetime import datetime
    last_time_str = get_last_intro_time(rubric)
    if not last_time_str:
        return False
    try:
        last_time = datetime.strptime(last_time_str, "%Y-%m-%dT%H:%M:%S")
        diff = (datetime.now() - last_time).total_seconds()
        return diff < 3600
    except Exception:
        return False

def update_last_intro(rubric: str):
    insert_memory('last_intro', 'yes', metadata=rubric)



