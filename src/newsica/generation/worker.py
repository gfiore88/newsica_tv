from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

from newsica.agents.ai_integrator import AIIntegratorAgent
from newsica.audio.ai_music_generator import generate_track
from newsica.storage.repositories import generation_jobs_repository as jobs

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_worker_id() -> str:
    return os.getenv("NEWSICA_REMOTE_WORKER_ID", "").strip() or f"worker-{os.getpid()}"


class SqliteJobBackend:
    def expire_stale_jobs(self, stale_seconds: int) -> dict:
        return jobs.expire_stale_jobs(stale_seconds)

    def claim_next_job(self, worker_id: str) -> dict | None:
        return jobs.claim_next_job(worker_id)

    def mark_running(self, job_id: str, worker_id: str) -> dict:
        return jobs.mark_running(job_id, worker_id)

    def heartbeat(self, job_id: str, worker_id: str) -> dict:
        return jobs.heartbeat(job_id, worker_id)

    def mark_uploading(self, job_id: str, worker_id: str, artifact_manifest: dict | None = None) -> dict:
        return jobs.mark_uploading(job_id, worker_id, artifact_manifest=artifact_manifest)

    def upload_artifact(self, job: dict, worker_id: str, artifact_manifest: dict) -> dict:
        return {"artifact_manifest": artifact_manifest}

    def mark_ready(self, job_id: str, worker_id: str, artifact_manifest: dict | None = None) -> dict:
        return jobs.mark_ready(job_id, worker_id, artifact_manifest=artifact_manifest)

    def mark_failed(self, job_id: str, worker_id: str, error: str) -> dict:
        return jobs.mark_failed(job_id, worker_id, error)


class HttpJobBackend:
    def __init__(self) -> None:
        self.base_url = _required_env("NEWSICA_REMOTE_GENERATION_URL").rstrip("/") + "/"
        self.token = _required_env("NEWSICA_REMOTE_GENERATION_TOKEN")

    def expire_stale_jobs(self, stale_seconds: int) -> dict:
        return {"reset": 0, "expired": 0}

    def claim_next_job(self, worker_id: str) -> dict | None:
        payload = self._post("api/generation/jobs/claim", {"worker_id": worker_id})
        return payload.get("job")

    def mark_running(self, job_id: str, worker_id: str) -> dict:
        return self._post(f"api/generation/jobs/{job_id}/running", {"worker_id": worker_id}).get("job")

    def heartbeat(self, job_id: str, worker_id: str) -> dict:
        return self._post(f"api/generation/jobs/{job_id}/heartbeat", {"worker_id": worker_id}).get("job")

    def mark_uploading(self, job_id: str, worker_id: str, artifact_manifest: dict | None = None) -> dict:
        return self._post(
            f"api/generation/jobs/{job_id}/uploading",
            {"worker_id": worker_id, "artifact_manifest": artifact_manifest},
        ).get("job")

    def upload_artifact(self, job: dict, worker_id: str, artifact_manifest: dict) -> dict:
        files = []
        opened_files = []
        try:
            manifest_payload = _portable_artifact_manifest(artifact_manifest)
            for path_text in _artifact_file_paths(artifact_manifest):
                path = Path(path_text)
                handle = path.open("rb")
                opened_files.append(handle)
                files.append(("files", (path.name, handle, "application/octet-stream")))
            response = requests.post(
                urljoin(self.base_url, f"api/generation/jobs/{job['id']}/artifact"),
                data={
                    "worker_id": worker_id,
                    "manifest_json": json.dumps(manifest_payload, ensure_ascii=False),
                },
                files=files,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=_env_int("NEWSICA_REMOTE_HTTP_TIMEOUT_SECONDS", 30),
            )
            response.raise_for_status()
            return response.json()
        finally:
            for handle in opened_files:
                handle.close()

    def mark_ready(self, job_id: str, worker_id: str, artifact_manifest: dict | None = None) -> dict:
        return self._post(
            f"api/generation/jobs/{job_id}/ready",
            {"worker_id": worker_id, "artifact_manifest": artifact_manifest},
        ).get("job")

    def mark_failed(self, job_id: str, worker_id: str, error: str) -> dict:
        return self._post(
            f"api/generation/jobs/{job_id}/failed",
            {"worker_id": worker_id, "error": error},
        ).get("job")

    def _post(self, path: str, payload: dict) -> dict:
        response = requests.post(
            urljoin(self.base_url, path),
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=_env_int("NEWSICA_REMOTE_HTTP_TIMEOUT_SECONDS", 30),
        )
        response.raise_for_status()
        return response.json()


def get_job_backend():
    transport = os.getenv("NEWSICA_REMOTE_WORKER_TRANSPORT", "sqlite").strip().lower()
    if transport == "sqlite":
        return SqliteJobBackend()
    if transport == "http":
        return HttpJobBackend()
    raise RuntimeError(f"Unsupported NEWSICA_REMOTE_WORKER_TRANSPORT={transport!r}")


def process_job(job: dict, worker_id: str, backend=None) -> dict:
    backend = backend or SqliteJobBackend()
    backend.mark_running(job["id"], worker_id)
    try:
        if job["job_type"] == "slot_audio":
            result = _process_slot_audio(job)
        elif job["job_type"] == "ai_music":
            result = _process_ai_music(job)
        else:
            raise RuntimeError(f"Unsupported generation job type: {job['job_type']}")

        backend.mark_uploading(job["id"], worker_id, artifact_manifest=result)
        upload_result = backend.upload_artifact(job, worker_id, result)
        final_manifest = upload_result.get("artifact_manifest") or result
        return backend.mark_ready(job["id"], worker_id, artifact_manifest=final_manifest)
    except Exception as e:
        logger.exception("Generation job %s failed", job.get("id"))
        return backend.mark_failed(job["id"], worker_id, str(e))


def run_worker(*, once: bool = False) -> None:
    worker_id = get_worker_id()
    poll_seconds = _env_int("NEWSICA_REMOTE_POLL_SECONDS", 10)
    idle_poll_seconds = _env_int("NEWSICA_REMOTE_IDLE_POLL_SECONDS", 30)
    stale_seconds = _env_int("NEWSICA_REMOTE_STALE_SECONDS", 300)
    backend = get_job_backend()
    logger.info("Generation worker started id=%s", worker_id)

    while True:
        recovery = backend.expire_stale_jobs(stale_seconds)
        if recovery.get("reset") or recovery.get("expired"):
            logger.info("Generation recovery: %s", recovery)

        job = backend.claim_next_job(worker_id)
        if job:
            logger.info("Claimed generation job %s type=%s", job["id"], job["job_type"])
            process_job(job, worker_id, backend=backend)
            if once:
                return
            time.sleep(poll_seconds)
            continue

        if once:
            return
        time.sleep(idle_poll_seconds)


def _process_slot_audio(job: dict) -> dict:
    payload = job.get("payload") or {}
    content_data = payload.get("content_data") or {}
    target_work_dir = payload.get("target_work_dir")

    is_http = os.getenv("NEWSICA_REMOTE_WORKER_TRANSPORT", "sqlite").strip().lower() == "http"
    if target_work_dir and not is_http:
        work_dir = Path(target_work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        return _generate_slot_audio_manifest(content_data, work_dir)

    with tempfile.TemporaryDirectory(prefix=f"newsica-job-{job['id']}-") as tmp:
        return _generate_slot_audio_manifest(content_data, Path(tmp))


def _generate_slot_audio_manifest(content_data: dict, work_dir: Path) -> dict:
    integrator = AIIntegratorAgent(work_dir=work_dir)
    script_text = integrator.generate_script(content_data)
    audio_files = integrator.generate_audio(script_text, content_data)
    if not audio_files:
        raise RuntimeError("slot_audio generation produced no files")
    return {
        "kind": "slot_audio",
        "work_dir": str(work_dir),
        "script_path": str(work_dir / "script.txt"),
        "audio_files": [str(Path(path)) for path in audio_files],
        "title": content_data.get("title"),
        "character": content_data.get("character_id") or content_data.get("character"),
        "slot_time": content_data.get("slot_time"),
        "theme": content_data.get("theme"),
    }


def _process_ai_music(job: dict) -> dict:
    payload = job.get("payload") or {}
    audio_file, title = generate_track(
        theme=payload.get("theme") or job.get("theme"),
        custom_brief=payload.get("custom_brief"),
        request_metadata=payload.get("request_metadata"),
    )
    if not audio_file:
        raise RuntimeError("ai_music generation produced no audio file")
    return {
        "kind": "ai_music",
        "audio_file": str(audio_file),
        "title": title,
        "theme": payload.get("theme") or job.get("theme"),
    }


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured in the environment")
    return value


def _artifact_file_paths(artifact_manifest: dict) -> list[str]:
    if artifact_manifest.get("kind") == "slot_audio":
        paths = list(artifact_manifest.get("audio_files") or [])
        script_path = artifact_manifest.get("script_path")
        if script_path:
            paths.append(script_path)
        return paths
    if artifact_manifest.get("kind") == "ai_music":
        audio_file = artifact_manifest.get("audio_file")
        return [audio_file] if audio_file else []
    return []


def _portable_artifact_manifest(artifact_manifest: dict) -> dict:
    manifest = dict(artifact_manifest)
    if manifest.get("kind") == "slot_audio":
        manifest["audio_files"] = [
            Path(path).name for path in manifest.get("audio_files") or []
        ]
        if manifest.get("script_path"):
            manifest["script_path"] = Path(manifest["script_path"]).name
    elif manifest.get("kind") == "ai_music" and manifest.get("audio_file"):
        manifest["audio_file"] = Path(manifest["audio_file"]).name
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="NewsicaTV generation job worker")
    parser.add_argument("--once", action="store_true", help="process at most one job and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
