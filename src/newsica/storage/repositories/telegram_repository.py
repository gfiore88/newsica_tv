import datetime
import uuid
import time
from newsica.storage.database import get_connection

def add_request(author_username: str, author_first_name: str, file_id: str, duration: int, original_path: str, converted_path: str, status: str = "pending"):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    voice_id = f"tgvoice_{uuid.uuid4().hex[:12]}"
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO telegram_requests (id, author_username, author_first_name, file_id, duration, original_path, converted_path, status, received_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (voice_id, author_username or "", author_first_name or "", file_id, duration, original_path, converted_path, status, now))
            conn.commit()
            return get_voice_by_id(voice_id)
    except Exception as e:
        print(f"⚠️ Errore db in telegram_requests add_request: {e}")
        return None

def update_status(id: str, status: str):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE telegram_requests 
                SET status = ?, processed_at = ?
                WHERE id = ?
            ''', (status, now, id))
            conn.commit()
            return get_voice_by_id(id)
    except Exception as e:
        print(f"⚠️ Errore db in telegram_requests update_status: {e}")
        return None

def get_voices_by_status(status: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM telegram_requests 
                WHERE status = ? 
                ORDER BY received_at ASC
            ''', (status,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"⚠️ Errore db in get_voices_by_status: {e}")
        return []

def get_all_voices():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM telegram_requests 
                ORDER BY received_at ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"⚠️ Errore db in get_all_voices: {e}")
        return []

def get_voice_by_id(id: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM telegram_requests 
                WHERE id = ?
            ''', (id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ Errore db in get_voice_by_id: {e}")
        return None

def consume_next_approved_voice():
    voices = get_voices_by_status("approved")
    if voices:
        voice = voices[0]
        update_status(voice["id"], "playing")
        return voice
    return None

def mark_played(id: str):
    return update_status(id, "played")

