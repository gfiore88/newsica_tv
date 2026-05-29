import sqlite3
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
DB_PATH = os.path.join(RUNTIME_DIR, "newsica.db")


class ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()

def get_connection():
    """
    Ritorna una connessione al DB SQLite con timeout di sicurezza
    per supportare accessi concorrenti da più processi.
    """
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0, factory=ManagedConnection)
    conn.row_factory = sqlite3.Row
    return conn

def init_schema():
    """
    Inizializza le tabelle base richieste per la Fase 3.
    L'aggiunta di ulteriori tabelle avverrà nelle fasi successive.
    """
    schema = """
    CREATE TABLE IF NOT EXISTS decision_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        level TEXT,
        message TEXT NOT NULL,
        context_json TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS broadcast_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_time TEXT,
        block_type TEXT,
        title TEXT,
        segment TEXT,
        event_type TEXT,
        asset_path TEXT,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        duration_seconds REAL,
        metadata_json TEXT
    );

    CREATE TABLE IF NOT EXISTS asset_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_time TEXT NOT NULL,
        character TEXT NOT NULL,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        ready_dir TEXT,
        manifest_path TEXT,
        error TEXT,
        prepared_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(slot_time, character)
    );

    CREATE TABLE IF NOT EXISTS telegram_requests (
        id TEXT PRIMARY KEY,
        author_username TEXT,
        author_first_name TEXT,
        file_id TEXT,
        duration INTEGER,
        original_path TEXT,
        converted_path TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        received_at TEXT NOT NULL,
        processed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS ai_music_jobs (
        id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL,
        source TEXT NOT NULL,
        theme TEXT,
        custom_brief TEXT,
        request_id TEXT,
        dedupe_key TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        audio_path TEXT,
        generated_title TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        failed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS generation_jobs (
        id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        priority INTEGER NOT NULL DEFAULT 0,
        slot_time TEXT,
        character TEXT,
        title TEXT,
        theme TEXT,
        source TEXT,
        dedupe_key TEXT,
        payload_json TEXT,
        artifact_manifest_json TEXT,
        error TEXT,
        deadline_at TEXT,
        worker_id TEXT,
        created_at TEXT NOT NULL,
        claimed_at TEXT,
        heartbeat_at TEXT,
        completed_at TEXT,
        failed_at TEXT,
        expired_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_generation_jobs_status_priority
        ON generation_jobs(status, priority DESC, deadline_at ASC, created_at ASC);

    CREATE INDEX IF NOT EXISTS idx_generation_jobs_dedupe_active
        ON generation_jobs(job_type, dedupe_key, status);

    CREATE TABLE IF NOT EXISTS chat_music_requests (
        id TEXT PRIMARY KEY,
        video_id TEXT NOT NULL,
        author TEXT NOT NULL,
        title TEXT,
        prompt TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        asset_path TEXT,
        error TEXT,
        received_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS daily_schedules (
        target_date TEXT PRIMARY KEY,
        schedule_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS news_articles (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT,
        category TEXT NOT NULL,
        published_at TEXT NOT NULL,
        is_breaking INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS editorial_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_type TEXT NOT NULL,
        value TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS audio_metadata (
        file_path TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        artist TEXT,
        album TEXT,
        duration INTEGER,
        metadata_json TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS shorts_library (
        filename TEXT PRIMARY KEY,
        video_path TEXT NOT NULL,
        mode TEXT NOT NULL,
        theme TEXT NOT NULL,
        news_title TEXT,
        script TEXT,
        caption TEXT,
        hashtags_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS shorts_daily_plans (
        target_date TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        reason TEXT,
        plan_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS shorts_daily_plan_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_date TEXT NOT NULL,
        mode TEXT NOT NULL,
        rule_type TEXT NOT NULL,
        reason TEXT,
        priority INTEGER NOT NULL DEFAULT 0,
        source_title TEXT,
        source_summary TEXT,
        source_score INTEGER,
        scheduled_for_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'planned',
        short_filename TEXT,
        publish_result_json TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(schema)
            shorts_columns = {
                row["name"] for row in cursor.execute("PRAGMA table_info(shorts_library)").fetchall()
            }
            if "social_posts_json" not in shorts_columns:
                cursor.execute(
                    "ALTER TABLE shorts_library ADD COLUMN social_posts_json TEXT DEFAULT '{}'"
                )
            conn.commit()
    except Exception as e:
        print(f"⚠️ Failed to initialize SQLite schema: {e}")

# Inizializza automaticamente lo schema quando il modulo viene importato
init_schema()
