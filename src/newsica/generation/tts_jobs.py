from __future__ import annotations

import os
import time
from pathlib import Path

from newsica.storage.repositories.generation_jobs_repository import enqueue_job, get_job


def remote_generation_enabled() -> bool:
    return os.getenv("NEWSICA_GENERATION_MODE", "local").strip().lower() == "remote"


def enqueue_audio_job(
    job_type: str,
    *,
    text: str,
    target_audio_path: str | Path | None = None,
    priority: int = 100,
    title: str | None = None,
    dedupe_key: str | None = None,
    payload: dict | None = None,
):
    data = dict(payload or {})
    data["text"] = text
    if target_audio_path is not None:
        data["target_audio_path"] = str(target_audio_path)
    return enqueue_job(
        job_type,
        priority=priority,
        title=title,
        dedupe_key=dedupe_key,
        payload=data,
    )


def wait_for_ready_job(job_id: str, *, timeout_seconds: int = 90, poll_seconds: float = 2.0) -> dict | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        job = get_job(job_id)
        if not job:
            return None
        if job.get("status") == "ready":
            return job
        if job.get("status") in {"failed", "expired"}:
            return None
        time.sleep(poll_seconds)
    return None


def enqueue_audio_job_and_wait(
    job_type: str,
    *,
    text: str,
    target_audio_path: str | Path,
    priority: int = 100,
    title: str | None = None,
    dedupe_key: str | None = None,
    payload: dict | None = None,
    timeout_seconds: int = 90,
) -> tuple[bool, dict | None]:
    job, _created = enqueue_audio_job(
        job_type,
        text=text,
        target_audio_path=target_audio_path,
        priority=priority,
        title=title,
        dedupe_key=dedupe_key,
        payload=payload,
    )
    ready_job = wait_for_ready_job(job["id"], timeout_seconds=timeout_seconds)
    target = Path(target_audio_path)
    return bool(ready_job and target.exists()), ready_job
