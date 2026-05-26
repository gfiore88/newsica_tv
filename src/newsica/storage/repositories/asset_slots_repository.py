import datetime
from newsica.storage.database import get_connection

def upsert_slot(slot_time: str, character: str, title: str, status: str, ready_dir: str = None, manifest_path: str = None, error: str = None):
    now = datetime.datetime.now().isoformat()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO asset_slots (slot_time, character, title, status, ready_dir, manifest_path, error, prepared_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slot_time, character) DO UPDATE SET
                    title = excluded.title,
                    status = excluded.status,
                    ready_dir = coalesce(excluded.ready_dir, asset_slots.ready_dir),
                    manifest_path = coalesce(excluded.manifest_path, asset_slots.manifest_path),
                    error = excluded.error,
                    prepared_at = coalesce(excluded.prepared_at, asset_slots.prepared_at),
                    updated_at = excluded.updated_at
            ''', (slot_time, character, title, status, ready_dir, manifest_path, error, None, now, now))
            conn.commit()
    except Exception as e:
        print(f"⚠️ Errore db in asset_slots upsert_slot: {e}")

def update_status(slot_time: str, character: str, status: str, error: str = None):
    now = datetime.datetime.now().isoformat()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE asset_slots 
                SET status = ?, error = ?, updated_at = ?
                WHERE slot_time = ? AND character = ?
            ''', (status, error, now, slot_time, character))
            conn.commit()
    except Exception as e:
        print(f"⚠️ Errore db in asset_slots update_status: {e}")
