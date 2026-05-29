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


def remote_llm_generate(
    prompt: str,
    *,
    system_prompt: str | None = None,
    options: dict | None = None,
    timeout_seconds: int = 60,
) -> str:
    """Accoda un job di tipo llm_generate e attende la risposta generata dal Mac Worker."""
    from newsica.storage.repositories.generation_jobs_repository import enqueue_job
    import hashlib

    payload = {
        "prompt": prompt,
        "system": system_prompt,
        "options": options or {},
    }
    # Generiamo una dedupe_key per evitare doppie generazioni contemporanee identiche
    dedupe_key = f"llm_generate:{hashlib.sha1((prompt + (system_prompt or '')).encode('utf-8')).hexdigest()[:16]}"

    job, _created = enqueue_job(
        "llm_generate",
        priority=110,
        title="LLM Prompt Generation",
        dedupe_key=dedupe_key,
        payload=payload,
    )

    ready_job = wait_for_ready_job(job["id"], timeout_seconds=timeout_seconds, poll_seconds=1.5)
    if ready_job:
        return (ready_job.get("artifact_manifest") or {}).get("text", "").strip()
    return ""

