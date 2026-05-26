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


import datetime
import os
import time
import uuid
from newsica.storage.repositories import ai_music_jobs_repository

ACTIVE_STATUSES = {"pending", "running"}
RUNNING_STALE_SECONDS = int(os.getenv("AI_MUSIC_RUNNING_STALE_SECONDS", "3600"))


def _parse_job_timestamp(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _expire_stale_running_jobs() -> None:
    if RUNNING_STALE_SECONDS <= 0:
        return
        
    running_jobs = ai_music_jobs_repository.get_running_jobs()
    now = datetime.datetime.now()
    
    for job in running_jobs:
        started_at = _parse_job_timestamp(job.get("started_at")) or _parse_job_timestamp(job.get("created_at"))
        if not started_at:
            continue
        age_seconds = (now - started_at).total_seconds()
        if age_seconds <= RUNNING_STALE_SECONDS:
            continue
            
        error_msg = (
            f"Job running orfano auto-chiuso dopo {int(age_seconds)}s "
            f"(soglia {RUNNING_STALE_SECONDS}s)"
        )[:400]
        
        ai_music_jobs_repository.update_job(
            job["id"], 
            status="failed", 
            failed_at=now.strftime("%Y-%m-%dT%H:%M:%S"),
            error=error_msg
        )


def list_jobs() -> list[dict]:
    _expire_stale_running_jobs()
    return ai_music_jobs_repository.get_all_jobs()


def find_active_job(
    *,
    job_type: str | None = None,
    dedupe_key: str | None = None,
) -> dict | None:
    _expire_stale_running_jobs()
    return ai_music_jobs_repository.get_active_job(job_type, dedupe_key)


def enqueue_job(
    *,
    job_type: str,
    source: str,
    theme: str | None = None,
    custom_brief: str | None = None,
    request_id: str | None = None,
    dedupe_key: str | None = None,
) -> tuple[dict, bool]:
    _expire_stale_running_jobs()
    
    if dedupe_key:
        active = ai_music_jobs_repository.get_active_job(dedupe_key=dedupe_key)
        if active:
            return active, False

    job_id = f"aijob_{int(time.time() * 1000)}"
    new_job = ai_music_jobs_repository.add_job(
        id=job_id,
        job_type=job_type,
        source=source,
        theme=theme,
        custom_brief=custom_brief,
        request_id=request_id,
        dedupe_key=dedupe_key,
        status="pending"
    )
    return new_job, True


def get_next_pending_job() -> dict | None:
    _expire_stale_running_jobs()
    return ai_music_jobs_repository.get_next_pending_job()


def update_job(
    job_id: str,
    **updates,
) -> dict | None:
    return ai_music_jobs_repository.update_job(job_id, **updates)


def mark_running(job_id: str) -> dict | None:
    return ai_music_jobs_repository.update_job(
        job_id,
        status="running",
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def mark_done(
    job_id: str,
    *,
    audio_path: str | None = None,
    title: str | None = None,
) -> dict | None:
    updates = {"status": "done", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if audio_path:
        updates["audio_path"] = audio_path
    if title:
        updates["generated_title"] = title
    return ai_music_jobs_repository.update_job(job_id, **updates)


def mark_failed(job_id: str, error: str) -> dict | None:
    return ai_music_jobs_repository.update_job(
        job_id,
        status="failed",
        failed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        error=error[:400],
    )
