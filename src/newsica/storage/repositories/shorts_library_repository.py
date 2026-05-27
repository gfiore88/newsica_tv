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
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO shorts_library (
                    filename, video_path, mode, theme, news_title, script, caption,
                    hashtags_json, social_posts_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    video_path=excluded.video_path,
                    mode=excluded.mode,
                    theme=excluded.theme,
                    news_title=excluded.news_title,
                    script=excluded.script,
                    caption=excluded.caption,
                    hashtags_json=excluded.hashtags_json,
                    social_posts_json=COALESCE(shorts_library.social_posts_json, excluded.social_posts_json),
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
                    "{}",
                    now,
                    now,
                ),
            )
            conn.commit()
    except Exception as e:
        print(f"⚠️ [SQLite] Errore salvataggio shorts_library: {e}")


def get_short(filename: str):
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM shorts_library WHERE filename = ?",
                (filename,),
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ [SQLite] Errore lettura shorts_library: {e}")
        return None


def delete_shorts(filenames: list[str]):
    if not filenames:
        return 0
    try:
        with get_connection() as conn:
            cursor = conn.executemany(
                "DELETE FROM shorts_library WHERE filename = ?",
                [(filename,) for filename in filenames],
            )
            conn.commit()
            return cursor.rowcount or 0
    except Exception as e:
        print(f"⚠️ [SQLite] Errore cancellazione shorts_library: {e}")
        return 0


def mark_short_social_posts(filename: str, platform_results: dict[str, dict], posted_at: str | None = None) -> dict:
    if not filename or not platform_results:
        return {}

    effective_posted_at = posted_at or datetime.now().isoformat()
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT social_posts_json FROM shorts_library WHERE filename = ?",
                (filename,),
            ).fetchone()
            if row is None:
                return {}

            try:
                social_posts = json.loads(row["social_posts_json"] or "{}")
            except Exception:
                social_posts = {}

            if not isinstance(social_posts, dict):
                social_posts = {}

            changed = False
            for platform, result in platform_results.items():
                if result.get("status") != "success":
                    continue
                social_posts[platform] = {
                    "posted_at": effective_posted_at,
                    "message": str(result.get("message", "")).strip(),
                }
                changed = True

            if not changed:
                return social_posts

            conn.execute(
                """
                UPDATE shorts_library
                SET social_posts_json = ?, updated_at = ?
                WHERE filename = ?
                """,
                (
                    json.dumps(social_posts, ensure_ascii=False),
                    effective_posted_at,
                    filename,
                ),
            )
            conn.commit()
            return social_posts
    except Exception as e:
        print(f"⚠️ [SQLite] Errore aggiornamento stato social short: {e}")
        return {}
