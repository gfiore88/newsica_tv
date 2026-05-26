from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from newsica.storage.repositories.ai_music_jobs_repository import enqueue_job

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
TMP_DIR = BASE_DIR / "tmp"
WORKER_SCRIPT = BASE_DIR / "src" / "newsica" / "audio" / "ai_music_worker.py"


def resolve_ace_step_python() -> str:
    candidates = [
        BASE_DIR / ".venv_ace_step" / "bin" / "python3",
        BASE_DIR / ".venv_ace_step" / "bin" / "python",
        BASE_DIR / "venv" / "bin" / "python3",
        BASE_DIR / "venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def launch_ai_music_worker() -> subprocess.Popen:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    log_path = TMP_DIR / "ai_music_worker.log"
    log_file = open(log_path, "a", encoding="utf-8")
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return subprocess.Popen(
        [resolve_ace_step_python(), "-u", str(WORKER_SCRIPT)],
        cwd=str(BASE_DIR),
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
        env=env,
    )


def schedule_rotation_fill_job(source: str, *, theme: str | None = None) -> tuple[dict, bool]:
    normalized_theme = " ".join(str(theme or "").strip().lower().split()) or None
    dedupe_key = "rotation_fill" if normalized_theme is None else None
    job, created = enqueue_job(
        job_type="rotation_fill",
        source=source,
        theme=normalized_theme,
        dedupe_key=dedupe_key,
    )
    launch_ai_music_worker()
    return job, created
