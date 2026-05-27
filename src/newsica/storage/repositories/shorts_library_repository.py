import json
from datetime import datetime

from newsica.storage.database import get_connection


def upsert_short(
    *,
    filename: str,
    video_path: str,
    mode: str,
    theme: str,
    news_title: str = "",
    script: str = "",
    caption: str = "",
    hashtags: list[str] | None = None,
):
    now = datetime.now().isoformat()
    hashtags_json = json.dumps(hashtags or [], ensure_ascii=False)
    conn = None
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO shorts_library (
                filename, video_path, mode, theme, news_title, script, caption,
                hashtags_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                video_path=excluded.video_path,
                mode=excluded.mode,
                theme=excluded.theme,
                news_title=excluded.news_title,
                script=excluded.script,
                caption=excluded.caption,
                hashtags_json=excluded.hashtags_json,
                updated_at=excluded.updated_at
            """,
            (
                filename,
                video_path,
                mode,
                theme,
                news_title,
                script,
                caption,
                hashtags_json,
                now,
                now,
            ),
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️ [SQLite] Errore salvataggio shorts_library: {e}")
    finally:
        if conn is not None:
            conn.close()


def get_short(filename: str):
    conn = None
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM shorts_library WHERE filename = ?",
            (filename,),
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ [SQLite] Errore lettura shorts_library: {e}")
        return None
    finally:
        if conn is not None:
            conn.close()


def delete_shorts(filenames: list[str]):
    if not filenames:
        return 0
    conn = None
    try:
        conn = get_connection()
        cursor = conn.executemany(
            "DELETE FROM shorts_library WHERE filename = ?",
            [(filename,) for filename in filenames],
        )
        conn.commit()
        return cursor.rowcount or 0
    except Exception as e:
        print(f"⚠️ [SQLite] Errore cancellazione shorts_library: {e}")
        return 0
    finally:
        if conn is not None:
            conn.close()
