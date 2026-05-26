#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))

from newsica.audio.ai_music_generator import generate_track, get_handlers
from newsica.storage.repositories.ai_music_jobs_repository import get_next_pending_job, mark_done, mark_failed, mark_running
from newsica.storage.repositories.chat_music_requests_repository import mark_failed as mark_chat_failed
from newsica.storage.repositories.chat_music_requests_repository import get_request, mark_generating, mark_ready

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (AiMusicWorker) %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOCK_FILE = BASE_DIR / "tmp" / "ai_music_worker.lock"
POLL_INTERVAL_SECONDS = 5


def acquire_worker_lock() -> bool:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)
            logger.info("Worker già attivo con PID %s. Esco.", pid)
            return False
        except (ValueError, ProcessLookupError, PermissionError):
            logger.warning("Lock worker orfano rilevato. Lo sostituisco.")
            LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_worker_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def prewarm_handlers() -> bool:
    try:
        logger.info("Prewarm ACE-Step: inizializzo tokenizer e modelli una sola volta.")
        get_handlers()
        logger.info("Prewarm ACE-Step completato.")
        return True
    except Exception as e:
        logger.error("Prewarm ACE-Step fallito: %s", e)
        return False


def process_job(job: dict) -> None:
    job_id = job["id"]
    request_id = job.get("request_id")
    mark_running(job_id)
    if job.get("job_type") == "chat_request" and request_id:
        mark_generating(request_id)

    logger.info(
        "Eseguo job %s type=%s source=%s theme=%s",
        job_id,
        job.get("job_type"),
        job.get("source"),
        job.get("theme"),
    )

    try:
        request_metadata = get_request(request_id) if request_id else None
        audio_file, title = generate_track(
            theme=job.get("theme"),
            custom_brief=job.get("custom_brief"),
            request_metadata=request_metadata,
        )
        if not audio_file:
            raise RuntimeError("generation returned no audio file")

        mark_done(job_id, audio_path=str(audio_file), title=title)
        if request_id:
            mark_ready(request_id, asset_path=str(audio_file), title=title)
        logger.info("Job %s completato: %s", job_id, audio_file.name)
    except Exception as e:
        message = str(e)
        mark_failed(job_id, message)
        if request_id:
            mark_chat_failed(request_id, message)
        logger.error("Job %s fallito: %s", job_id, message)


def run_worker() -> None:
    prewarm_ok = prewarm_handlers()
    if not prewarm_ok:
        logger.warning("Continuo comunque: ritenterò implicitamente al primo job.")

    while True:
        job = get_next_pending_job()
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        process_job(job)


if __name__ == "__main__":
    if not acquire_worker_lock():
        sys.exit(0)
    try:
        logger.info("Worker musica AI persistente avviato.")
        run_worker()
    finally:
        release_worker_lock()
