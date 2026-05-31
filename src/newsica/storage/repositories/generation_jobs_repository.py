import datetime
import json
import uuid

from newsica.storage.database import get_connection

ACTIVE_STATUSES = ("pending", "claimed", "running", "uploading")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _decode(row):
    if not row:
        return None
    data = dict(row)
    for key in ("payload_json", "artifact_manifest_json"):
        value = data.get(key)
        if value:
            try:
                data[key.removesuffix("_json")] = json.loads(value)
            except Exception:
                data[key.removesuffix("_json")] = None
        else:
            data[key.removesuffix("_json")] = None
    return data


def enqueue_job(
    job_type,
    *,
    priority=0,
    slot_time=None,
    character=None,
    title=None,
    theme=None,
    source=None,
    dedupe_key=None,
    payload=None,
    deadline_at=None,
):
    if dedupe_key:
        active = get_active_job(job_type=job_type, dedupe_key=dedupe_key)
        if active:
            return active, False

    job_id = str(uuid.uuid4())[:12]
    now = _now()
    payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO generation_jobs (
                id, job_type, status, priority, slot_time, character, title, theme,
                source, dedupe_key, payload_json, deadline_at, created_at
            )
            VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                job_type,
                int(priority or 0),
                slot_time,
                character,
                title,
                theme,
                source,
                dedupe_key,
                payload_json,
                deadline_at,
                now,
            ),
        )
        conn.commit()
    return get_job(job_id), True


def get_job(job_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
    return _decode(row)


def get_active_job(job_type=None, dedupe_key=None):
    query = "SELECT * FROM generation_jobs WHERE status IN (?, ?, ?, ?)"
    params = list(ACTIVE_STATUSES)
    if job_type:
        query += " AND job_type = ?"
        params.append(job_type)
    if dedupe_key:
        query += " AND dedupe_key = ?"
        params.append(dedupe_key)
    query += " ORDER BY created_at ASC LIMIT 1"
    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
    return _decode(row)


def claim_next_job(worker_id, *, job_types=None):
    now = _now()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        query = "SELECT * FROM generation_jobs WHERE status = 'pending'"
        params = []
        if job_types:
            placeholders = ",".join("?" for _ in job_types)
            query += f" AND job_type IN ({placeholders})"
            params.extend(job_types)
        query += " ORDER BY priority DESC, deadline_at ASC, created_at ASC LIMIT 1"
        row = cursor.execute(query, params).fetchone()
        if not row:
            conn.commit()
            return None
        job_id = row["id"]
        cursor.execute(
            """
            UPDATE generation_jobs
            SET status = 'claimed', worker_id = ?, claimed_at = ?, heartbeat_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (worker_id, now, now, job_id),
        )
        conn.commit()
    return get_job(job_id)


def mark_running(job_id, worker_id):
    return _update_owned_job(
        job_id,
        worker_id,
        status="running",
        started_at=_now(),
        heartbeat_at=_now(),
    )


def heartbeat(job_id, worker_id):
    return _update_owned_job(job_id, worker_id, heartbeat_at=_now())


def mark_uploading(job_id, worker_id, artifact_manifest=None):
    updates = {"status": "uploading", "heartbeat_at": _now()}
    if artifact_manifest is not None:
        updates["artifact_manifest_json"] = json.dumps(artifact_manifest, ensure_ascii=False, sort_keys=True)
    return _update_owned_job(job_id, worker_id, **updates)


def mark_ready(job_id, worker_id, artifact_manifest=None):
    updates = {
        "status": "ready",
        "completed_at": _now(),
        "ended_at": _now(),
        "heartbeat_at": _now(),
        "error": None,
    }
    if artifact_manifest is not None:
        updates["artifact_manifest_json"] = json.dumps(artifact_manifest, ensure_ascii=False, sort_keys=True)
    return _update_owned_job(job_id, worker_id, **updates)


def mark_failed(job_id, worker_id, error):
    return _update_owned_job(
        job_id,
        worker_id,
        status="failed",
        error=str(error),
        failed_at=_now(),
        ended_at=_now(),
        heartbeat_at=_now(),
    )


def expire_stale_jobs(stale_seconds):
    cutoff = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(seconds=int(stale_seconds))
    ).replace(microsecond=0).isoformat()
    now = _now()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE generation_jobs
            SET status = 'pending', worker_id = NULL, claimed_at = NULL, heartbeat_at = NULL,
                error = 'stale worker heartbeat; job returned to pending'
            WHERE status IN ('claimed', 'running', 'uploading')
              AND heartbeat_at IS NOT NULL
              AND heartbeat_at < ?
            """,
            (cutoff,),
        )
        reset_count = cursor.rowcount
        cursor.execute(
            """
            UPDATE generation_jobs
            SET status = 'expired', expired_at = ?, ended_at = ?, error = 'deadline expired'
            WHERE status IN ('pending', 'claimed', 'running', 'uploading')
              AND deadline_at IS NOT NULL
              AND deadline_at < ?
            """,
            (now, now, now),
        )
        expired_count = cursor.rowcount
        conn.commit()
    return {"reset": reset_count, "expired": expired_count}


def list_jobs(status=None, limit=50):
    query = "SELECT * FROM generation_jobs"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_decode(row) for row in rows]


def get_summary():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM generation_jobs
            GROUP BY status
            """
        ).fetchall()
        active_workers = conn.execute(
            """
            SELECT worker_id, COUNT(*) AS active_jobs, MAX(heartbeat_at) AS last_heartbeat_at
            FROM generation_jobs
            WHERE worker_id IS NOT NULL AND status IN ('claimed', 'running', 'uploading')
            GROUP BY worker_id
            ORDER BY last_heartbeat_at DESC
            """
        ).fetchall()
        latest_jobs = conn.execute(
            """
            SELECT *
            FROM generation_jobs
            ORDER BY created_at DESC
            LIMIT 10
            """
        ).fetchall()
    return {
        "counts": {row["status"]: row["count"] for row in rows},
        "active_workers": [dict(row) for row in active_workers],
        "latest_jobs": [_decode(row) for row in latest_jobs],
    }


def _update_owned_job(job_id, worker_id, **updates):
    if not updates:
        return get_job(job_id)
    keys = list(updates.keys())
    set_clause = ", ".join(f"{key} = ?" for key in keys)
    values = [updates[key] for key in keys]
    values.extend([job_id, worker_id])
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE generation_jobs
            SET {set_clause}
            WHERE id = ? AND worker_id = ?
            """,
            values,
        )
        conn.commit()
    return get_job(job_id)
