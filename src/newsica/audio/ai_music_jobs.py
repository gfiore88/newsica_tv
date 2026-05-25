from __future__ import annotations

import datetime
import json
import os
import time
from pathlib import Path

from newsica.config.paths import RUNTIME_DIR

JOBS_FILE = RUNTIME_DIR / "ai_music_jobs.json"
ACTIVE_STATUSES = {"pending", "running"}
RUNNING_STALE_SECONDS = int(os.getenv("AI_MUSIC_RUNNING_STALE_SECONDS", "3600"))


def _parse_job_timestamp(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _expire_stale_running_jobs(payload: dict) -> bool:
    if RUNNING_STALE_SECONDS <= 0:
        return False

    changed = False
    now = datetime.datetime.now()
    for job in payload.get("jobs", []):
        if job.get("status") != "running":
            continue
        started_at = _parse_job_timestamp(job.get("started_at")) or _parse_job_timestamp(job.get("created_at"))
        if not started_at:
            continue
        age_seconds = (now - started_at).total_seconds()
        if age_seconds <= RUNNING_STALE_SECONDS:
            continue
        job["status"] = "failed"
        job["failed_at"] = now.strftime("%Y-%m-%dT%H:%M:%S")
        job["error"] = (
            f"Job running orfano auto-chiuso dopo {int(age_seconds)}s "
            f"(soglia {RUNNING_STALE_SECONDS}s)"
        )[:400]
        changed = True
    return changed


def _load_payload(path: Path = JOBS_FILE) -> dict:
    if not path.exists():
        return {"jobs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"jobs": []}
    if not isinstance(data, dict):
        return {"jobs": []}
    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        data["jobs"] = []
    if _expire_stale_running_jobs(data):
        _save_payload(data, path)
    return data


def _save_payload(payload: dict, path: Path = JOBS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def list_jobs(path: Path = JOBS_FILE) -> list[dict]:
    return list(_load_payload(path).get("jobs", []))


def find_active_job(
    *,
    job_type: str | None = None,
    dedupe_key: str | None = None,
    path: Path = JOBS_FILE,
) -> dict | None:
    for job in _load_payload(path).get("jobs", []):
        if job.get("status") not in ACTIVE_STATUSES:
            continue
        if job_type and job.get("job_type") != job_type:
            continue
        if dedupe_key and job.get("dedupe_key") != dedupe_key:
            continue
        return dict(job)
    return None


def enqueue_job(
    *,
    job_type: str,
    source: str,
    theme: str | None = None,
    custom_brief: str | None = None,
    request_id: str | None = None,
    dedupe_key: str | None = None,
    path: Path = JOBS_FILE,
) -> tuple[dict, bool]:
    payload = _load_payload(path)
    if dedupe_key:
        for job in payload.get("jobs", []):
            if job.get("status") in ACTIVE_STATUSES and job.get("dedupe_key") == dedupe_key:
                return dict(job), False

    job = {
        "id": f"aijob_{int(time.time() * 1000)}",
        "job_type": job_type,
        "source": source,
        "theme": theme,
        "custom_brief": custom_brief,
        "request_id": request_id,
        "dedupe_key": dedupe_key,
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    payload["jobs"].append(job)
    _save_payload(payload, path)
    return job, True


def get_next_pending_job(path: Path = JOBS_FILE) -> dict | None:
    for job in _load_payload(path).get("jobs", []):
        if job.get("status") == "pending":
            return dict(job)
    return None


def update_job(
    job_id: str,
    *,
    path: Path = JOBS_FILE,
    **updates,
) -> dict | None:
    payload = _load_payload(path)
    for job in payload.get("jobs", []):
        if job.get("id") != job_id:
            continue
        job.update(updates)
        _save_payload(payload, path)
        return dict(job)
    return None


def mark_running(job_id: str, path: Path = JOBS_FILE) -> dict | None:
    return update_job(
        job_id,
        path=path,
        status="running",
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def mark_done(
    job_id: str,
    *,
    audio_path: str | None = None,
    title: str | None = None,
    path: Path = JOBS_FILE,
) -> dict | None:
    payload = {"status": "done", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if audio_path:
        payload["audio_path"] = audio_path
    if title:
        payload["generated_title"] = title
    return update_job(job_id, path=path, **payload)


def mark_failed(job_id: str, error: str, path: Path = JOBS_FILE) -> dict | None:
    return update_job(
        job_id,
        path=path,
        status="failed",
        failed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        error=error[:400],
    )
