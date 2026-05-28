import json
import time
from datetime import datetime, timedelta, timezone

from newsica.storage.database import get_connection


def save_daily_plan(target_date: str, status: str, reason: str, plan_payload: dict, items: list[dict]) -> bool:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    plan_json = json.dumps(plan_payload or {}, ensure_ascii=False)
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO shorts_daily_plans (target_date, status, reason, plan_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(target_date) DO UPDATE SET
                    status=excluded.status,
                    reason=excluded.reason,
                    plan_json=excluded.plan_json,
                    updated_at=excluded.updated_at
                """,
                (target_date, status, reason, plan_json, now, now),
            )
            conn.execute("DELETE FROM shorts_daily_plan_items WHERE target_date = ?", (target_date,))
            for item in items:
                conn.execute(
                    """
                    INSERT INTO shorts_daily_plan_items (
                        target_date, mode, rule_type, reason, priority, source_title, source_summary,
                        source_score, scheduled_for_json, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        target_date,
                        item.get("mode", "news"),
                        item.get("rule_type", "always"),
                        item.get("reason", ""),
                        int(item.get("priority", 0)),
                        item.get("source_title", ""),
                        item.get("source_summary", ""),
                        int(item.get("source_score", 0)),
                        json.dumps(item.get("scheduled_for", {}), ensure_ascii=False),
                        item.get("status", "planned"),
                        now,
                        now,
                    ),
                )
            conn.commit()
            return True
    except Exception as e:
        print(f"⚠️ [SQLite] Errore salvataggio piano shorts: {e}")
        return False


def get_daily_plan(target_date: str) -> dict | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM shorts_daily_plans WHERE target_date = ?",
                (target_date,),
            ).fetchone()
            if not row:
                return None
            payload = dict(row)
            try:
                payload["plan_json"] = json.loads(payload.get("plan_json") or "{}")
            except Exception:
                payload["plan_json"] = {}
            return payload
    except Exception as e:
        print(f"⚠️ [SQLite] Errore lettura piano shorts: {e}")
        return None


def list_plan_items(target_date: str) -> list[dict]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM shorts_daily_plan_items
                WHERE target_date = ?
                ORDER BY priority DESC, id ASC
                """,
                (target_date,),
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                try:
                    item["scheduled_for"] = json.loads(item.get("scheduled_for_json") or "{}")
                except Exception:
                    item["scheduled_for"] = {}
                try:
                    item["publish_result"] = json.loads(item.get("publish_result_json") or "{}")
                except Exception:
                    item["publish_result"] = {}
                items.append(item)
            return items
    except Exception as e:
        print(f"⚠️ [SQLite] Errore lettura items piano shorts: {e}")
        return []


def _parse_utc(value: str) -> datetime | None:
    try:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _earliest_due_utc(scheduled_for: dict) -> datetime | None:
    if not isinstance(scheduled_for, dict):
        return None
    due_times = []
    for payload in scheduled_for.values():
        if not isinstance(payload, dict):
            continue
        due_dt = _parse_utc(payload.get("utc"))
        if due_dt:
            due_times.append(due_dt)
    if not due_times:
        return None
    return min(due_times)


def get_pending_generation_items(limit: int = 1, due_within_minutes: int | None = None) -> list[dict]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM shorts_daily_plan_items
                WHERE status = 'planned'
                ORDER BY target_date ASC, priority DESC, id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                try:
                    item["scheduled_for"] = json.loads(item.get("scheduled_for_json") or "{}")
                except Exception:
                    item["scheduled_for"] = {}
                item["_earliest_due_utc"] = _earliest_due_utc(item["scheduled_for"])
                items.append(item)
            if due_within_minutes is not None:
                now_utc = datetime.now(timezone.utc)
                cutoff_utc = now_utc + timedelta(minutes=max(0, int(due_within_minutes)))
                filtered = []
                for item in items:
                    earliest_due = item.get("_earliest_due_utc")
                    if earliest_due is None or earliest_due <= cutoff_utc:
                        filtered.append(item)
                items = filtered
            far_future = datetime.max.replace(tzinfo=timezone.utc)
            items.sort(
                key=lambda item: (
                    item.get("_earliest_due_utc") or far_future,
                    -int(item.get("priority", 0)),
                    int(item.get("id", 0)),
                )
            )
            for item in items:
                item.pop("_earliest_due_utc", None)
            items = items[: max(0, int(limit))]
            return items
    except Exception as e:
        print(f"⚠️ [SQLite] Errore lettura queue shorts: {e}")
        return []


def update_item_status(item_id: int, status: str, **extra) -> bool:
    allowed = {"short_filename", "publish_result_json", "error"}
    fields = {"status": status, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    for key, value in extra.items():
        if key in allowed:
            fields[key] = value

    set_clause = ", ".join([f"{key} = ?" for key in fields.keys()])
    values = list(fields.values()) + [item_id]
    try:
        with get_connection() as conn:
            conn.execute(
                f"UPDATE shorts_daily_plan_items SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"⚠️ [SQLite] Errore update item shorts #{item_id}: {e}")
        return False


def add_plan_item(target_date: str, item: dict) -> bool:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO shorts_daily_plan_items (
                    target_date, mode, rule_type, reason, priority, source_title, source_summary,
                    source_score, scheduled_for_json, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_date,
                    item.get("mode", "breaking"),
                    item.get("rule_type", "extra"),
                    item.get("reason", "breaking_extra"),
                    int(item.get("priority", 120)),
                    item.get("source_title", ""),
                    item.get("source_summary", ""),
                    int(item.get("source_score", 0)),
                    json.dumps(item.get("scheduled_for", {}), ensure_ascii=False),
                    item.get("status", "planned"),
                    now,
                    now,
                ),
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"⚠️ [SQLite] Errore insert item piano shorts: {e}")
        return False


def summarize_plan_status(target_date: str) -> dict:
    summary = {"planned": 0, "generating": 0, "scheduled": 0, "failed": 0, "skipped": 0, "posted": 0}
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) as total
                FROM shorts_daily_plan_items
                WHERE target_date = ?
                GROUP BY status
                """,
                (target_date,),
            ).fetchall()
            for row in rows:
                key = str(row["status"] or "").strip().lower()
                if key not in summary:
                    summary[key] = 0
                summary[key] = int(row["total"] or 0)
            return summary
    except Exception as e:
        print(f"⚠️ [SQLite] Errore summary piano shorts: {e}")
        return summary
