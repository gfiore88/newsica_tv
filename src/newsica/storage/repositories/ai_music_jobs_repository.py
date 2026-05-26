import time
import uuid
from newsica.storage.database import get_connection

def enqueue_job(job_type: str, source: str, theme: str = None, custom_brief: str = None, request_id: str = None, dedupe_key: str = None):
    if dedupe_key:
        active = get_active_job(job_type=job_type, dedupe_key=dedupe_key)
        if active:
            return active, False
            
    job_id = str(uuid.uuid4())[:8]
    job = add_job(
        id=job_id,
        job_type=job_type,
        source=source,
        theme=theme,
        custom_brief=custom_brief,
        request_id=request_id,
        dedupe_key=dedupe_key,
        status="pending"
    )
    return job, True

def list_jobs():
    return get_all_jobs()

def add_job(id: str, job_type: str, source: str, theme: str = None, custom_brief: str = None, request_id: str = None, dedupe_key: str = None, status: str = "pending"):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ai_music_jobs (id, job_type, source, theme, custom_brief, request_id, dedupe_key, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id, job_type, source, theme, custom_brief, request_id, dedupe_key, status, now))
            conn.commit()
            return get_job_by_id(id)
    except Exception as e:
        print(f"⚠️ Errore db in add_job: {e}")
        return None

def update_job(id: str, **updates):
    if not updates:
        return get_job_by_id(id)
    try:
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values())
        values.append(id)
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE ai_music_jobs 
                SET {set_clause}
                WHERE id = ?
            ''', values)
            conn.commit()
            return get_job_by_id(id)
    except Exception as e:
        print(f"⚠️ Errore db in update_job: {e}")
        return None

def get_job_by_id(id: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ai_music_jobs WHERE id = ?', (id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ Errore db in get_job_by_id: {e}")
        return None

def get_active_job(job_type: str = None, dedupe_key: str = None):
    try:
        query = "SELECT * FROM ai_music_jobs WHERE status IN ('pending', 'running')"
        params = []
        if job_type:
            query += " AND job_type = ?"
            params.append(job_type)
        if dedupe_key:
            query += " AND dedupe_key = ?"
            params.append(dedupe_key)
            
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ Errore db in get_active_job: {e}")
        return None

def get_next_pending_job():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_music_jobs WHERE status = 'pending' ORDER BY created_at ASC")
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ Errore db in get_next_pending_job: {e}")
        return None

def get_all_jobs():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_music_jobs ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"⚠️ Errore db in get_all_jobs: {e}")
        return []

def get_running_jobs():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_music_jobs WHERE status = 'running'")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"⚠️ Errore db in get_running_jobs: {e}")
        return []


def mark_running(id: str):
    return update_job(id, status="running", started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))


def mark_done(id: str, audio_path: str, title: str):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    return update_job(
        id,
        status="done",
        audio_path=audio_path,
        generated_title=title,
        completed_at=now,
        failed_at=None,
        error=None,
    )


def mark_failed(id: str, error: str):
    return update_job(
        id,
        status="failed",
        error=error,
        failed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
