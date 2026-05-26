import sqlite3
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
DB_PATH = os.path.join(RUNTIME_DIR, "newsica.db")

def get_connection():
    """
    Ritorna una connessione al DB SQLite con timeout di sicurezza
    per supportare accessi concorrenti da più processi.
    """
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
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

    CREATE TABLE IF NOT EXISTS editorial_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_type TEXT NOT NULL,
        value TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT NOT NULL
    );
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(schema)
            conn.commit()
    except Exception as e:
        print(f"⚠️ Failed to initialize SQLite schema: {e}")

# Inizializza automaticamente lo schema quando il modulo viene importato
init_schema()
