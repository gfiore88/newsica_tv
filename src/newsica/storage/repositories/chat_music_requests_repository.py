import time
from newsica.storage.database import get_connection

def add_request(id: str, video_id: str, author: str, title: str = None, prompt: str = None, status: str = "pending"):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chat_music_requests (id, video_id, author, title, prompt, status, received_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (id, video_id, author, title, prompt, status, now))
            conn.commit()
            return get_request_by_id(id)
    except Exception as e:
        print(f"⚠️ Errore db in add_request: {e}")
        return None

def update_request(id: str, **updates):
    if not updates:
        return get_request_by_id(id)
    try:
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values())
        values.append(id)
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE chat_music_requests 
                SET {set_clause}
                WHERE id = ?
            ''', values)
            conn.commit()
            return get_request_by_id(id)
    except Exception as e:
        print(f"⚠️ Errore db in update_request: {e}")
        return None

def get_request_by_id(id: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM chat_music_requests WHERE id = ?', (id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ Errore db in get_request_by_id: {e}")
        return None

def get_next_request_by_status(status: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_music_requests WHERE status = ? ORDER BY received_at ASC", (status,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ Errore db in get_next_request_by_status: {e}")
        return None

def get_all_requests():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_music_requests ORDER BY received_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"⚠️ Errore db in get_all_requests: {e}")
        return []

def enqueue_request(id: str, video_id: str, author: str, prompt: str):
    return add_request(id, video_id, author, prompt=prompt, status="pending")

def mark_generating(id: str):
    return update_request(id, status="generating")

def mark_ready(id: str, asset_path: str, title: str):
    return update_request(id, status="ready", asset_path=asset_path, title=title)

def mark_failed(id: str, error: str):
    return update_request(id, status="failed", error=error)

def consume_next_ready_request():
    req = get_next_request_by_status("ready")
    if req:
        update_request(req["id"], status="played")
        return req
    return None
