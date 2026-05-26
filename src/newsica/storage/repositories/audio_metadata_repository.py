import time
import json
from newsica.storage.database import get_connection

def save_metadata(file_path: str, title: str, artist: str = "", album: str = "", duration: int = 0, metadata: dict = None):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audio_metadata (file_path, title, artist, album, duration, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    title=excluded.title,
                    artist=excluded.artist,
                    album=excluded.album,
                    duration=excluded.duration,
                    metadata_json=excluded.metadata_json
            ''', (file_path, title, artist, album, duration, metadata_json, now))
            conn.commit()
            return True
    except Exception as e:
        print(f"⚠️ Errore db in save_metadata: {e}")
        return False

def get_metadata(file_path: str) -> dict | None:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM audio_metadata WHERE file_path = ?', (file_path,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                if res.get("metadata_json"):
                    res["metadata"] = json.loads(res["metadata_json"])
                return res
            return None
    except Exception as e:
        print(f"⚠️ Errore db in get_metadata: {e}")
        return None

def delete_metadata(file_path: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM audio_metadata WHERE file_path = ?', (file_path,))
            conn.commit()
            return True
    except Exception as e:
        print(f"⚠️ Errore db in delete_metadata: {e}")
        return False
