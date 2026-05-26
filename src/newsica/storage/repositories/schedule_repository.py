import time
import json
from newsica.storage.database import get_connection

def save_schedule(target_date: str, schedule_data: dict):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    schedule_json = json.dumps(schedule_data, ensure_ascii=False)
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Upsert
            cursor.execute('''
                INSERT INTO daily_schedules (target_date, schedule_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(target_date) DO UPDATE SET
                    schedule_json=excluded.schedule_json,
                    updated_at=excluded.updated_at
            ''', (target_date, schedule_json, now, now))
            conn.commit()
            return True
    except Exception as e:
        print(f"⚠️ Errore db in save_schedule: {e}")
        return False

def get_schedule(target_date: str) -> dict | None:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT schedule_json FROM daily_schedules WHERE target_date = ?', (target_date,))
            row = cursor.fetchone()
            if row:
                return json.loads(row['schedule_json'])
            return None
    except Exception as e:
        print(f"⚠️ Errore db in get_schedule: {e}")
        return None
