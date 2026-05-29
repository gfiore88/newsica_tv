from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

from newsica.agents.ai_integrator import AIIntegratorAgent
from newsica.audio.ai_music_generator import generate_track
from newsica.audio.settings import resolve_ffmpeg_cmd
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
        elif job["job_type"] == "hourly_chime":
            result = _process_hourly_chime(job)
        elif job["job_type"] == "short_tts":
            result = _process_short_tts(job)
        elif job["job_type"] == "tts_audio":
            result = _process_tts_audio(job)
        elif job["job_type"] == "breaking_news":
            result = _process_breaking_news(job)
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

    tmp = tempfile.mkdtemp(prefix=f"newsica-job-{job['id']}-")
    return _generate_slot_audio_manifest(content_data, Path(tmp))


def _generate_slot_audio_manifest(content_data: dict, work_dir: Path) -> dict:
    integrator = AIIntegratorAgent(work_dir=work_dir)
    script_text = integrator.generate_script(content_data)
    audio_files = list(integrator.generate_audio(script_text, content_data))
    if not audio_files:
        raise RuntimeError("slot_audio generation produced no files")
    primary_audio = _prepare_primary_audio_file(audio_files, work_dir)
    return {
        "kind": "slot_audio",
        "work_dir": str(work_dir),
        "script_path": str(work_dir / "script.txt"),
        "audio_files": [str(Path(path)) for path in audio_files],
        "primary_audio": str(primary_audio) if primary_audio else None,
        "title": content_data.get("title"),
        "character": content_data.get("character_id") or content_data.get("character"),
        "slot_time": content_data.get("slot_time"),
        "theme": content_data.get("theme"),
    }


def _prepare_primary_audio_file(audio_files: list[Path], work_dir: Path) -> Path | None:
    target = work_dir / "audio.wav"
    if target.exists():
        return target

    part_files = sorted(
        [
            Path(path)
            for path in audio_files
            if Path(path).name.startswith("audio_part") and Path(path).suffix == ".wav"
        ],
        key=lambda path: path.name,
    )
    if part_files:
        _concat_audio_files(part_files, target)
        audio_files.append(target)
        return target

    first_wav = next((Path(path) for path in audio_files if Path(path).suffix == ".wav"), None)
    if first_wav:
        if first_wav == target:
            return target
        shutil.copy2(first_wav, target)
        audio_files.append(target)
        return target
    return None


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


def _process_hourly_chime(job: dict) -> dict:
    """Genera il segnale orario: TTS della voce + concatenazione con il jingle."""
    payload = job.get("payload") or {}
    text = payload.get("text") or ""
    if not text:
        raise RuntimeError("hourly_chime job missing 'text' in payload")

    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    jingle_file = base_dir / "assets" / "jingles" / "jingle_ora_esatta.mp3"
    if not jingle_file.exists():
        raise RuntimeError(f"Jingle file not found: {jingle_file}")

    tmp_path = Path(tempfile.mkdtemp(prefix=f"newsica-chime-{job['id']}-"))
    voice_file = tmp_path / "chime_voice.wav"
    output_file = tmp_path / "hourly_chime.wav"
    _synthesize_kokoro(text, voice_file, character="breaking_news", voice="if_sara", speed=0.95)
    _concat_audio_files([jingle_file, voice_file], output_file)
    return {
        "kind": "hourly_chime",
        "audio_file": str(output_file),
        "text": text,
        "auto_play": payload.get("auto_play", True),
    }


def _process_short_tts(job: dict) -> dict:
    """Genera solo l'audio TTS per uno Short (il rendering video resta sul VPS)."""
    payload = job.get("payload") or {}
    text = payload.get("text") or ""
    if not text:
        raise RuntimeError("short_tts job missing 'text' in payload")

    speed = float(payload.get("speed", 1.1))
    tmp_path = Path(tempfile.mkdtemp(prefix=f"newsica-short-tts-{job['id']}-"))
    audio_file = tmp_path / "short_audio.wav"
    duration, resolved_voice = _synthesize_kokoro(
        text,
        audio_file,
        character=payload.get("character") or "chiara",
        voice=payload.get("voice"),
        speed=speed,
    )
    return {
        "kind": "short_tts",
        "audio_file": str(audio_file),
        "duration": duration,
        "text": text,
        "voice": resolved_voice,
        "speed": speed,
    }


def _process_tts_audio(job: dict) -> dict:
    payload = job.get("payload") or {}
    text = payload.get("text") or ""
    if not text:
        raise RuntimeError("tts_audio job missing 'text' in payload")
    tmp_path = Path(tempfile.mkdtemp(prefix=f"newsica-tts-{job['id']}-"))
    audio_file = tmp_path / "tts_audio.wav"
    duration, resolved_voice = _synthesize_kokoro(
        text,
        audio_file,
        character=payload.get("character") or "breaking_news",
        voice=payload.get("voice"),
        speed=float(payload.get("speed", 0.95)),
    )
    return {
        "kind": "tts_audio",
        "audio_file": str(audio_file),
        "duration": duration,
        "text": text,
        "voice": resolved_voice,
    }


def _process_breaking_news(job: dict) -> dict:
    payload = job.get("payload") or {}
    text = payload.get("text") or ""
    if not text:
        raise RuntimeError("breaking_news job missing 'text' in payload")
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    jingle_file = Path(payload.get("jingle_path") or base_dir / "assets" / "jingles" / "jingle_breaking_news.mp3")
    tmp_path = Path(tempfile.mkdtemp(prefix=f"newsica-breaking-{job['id']}-"))
    voice_file = tmp_path / "voice_breaking.wav"
    alarm_file = tmp_path / "alarm_jingle.wav"
    output_file = tmp_path / "breaking_news.wav"
    _synthesize_kokoro(
        text,
        voice_file,
        character=payload.get("character") or "breaking_news",
        speed=float(payload.get("speed", 1.1)),
    )
    if jingle_file.exists():
        _convert_audio(jingle_file, alarm_file)
    else:
        _generate_alarm_fallback(alarm_file)
    _concat_audio_files([alarm_file, voice_file], output_file)
    return {
        "kind": "breaking_news",
        "audio_file": str(output_file),
        "text": text,
        "severity_score": payload.get("severity_score", 0),
        "reason": payload.get("reason", ""),
    }


def _synthesize_kokoro(text: str, output_file: Path, *, character: str, speed: float, voice: str | None = None) -> tuple[float, str]:
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
        from newsica.utils.voice_helper import get_voice_style_for_character

        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        kokoro = Kokoro(str(base_dir / "kokoro-v1.0.onnx"), str(base_dir / "voices-v1.0.bin"))
        resolved_voice = voice or get_voice_style_for_character(kokoro, character)
        samples, sample_rate = kokoro.create(text, voice=resolved_voice, speed=speed, lang="it")
        sf.write(str(output_file), samples, sample_rate)
        return len(samples) / sample_rate, resolved_voice
    except Exception as e:
        raise RuntimeError(f"Kokoro TTS generation failed: {e}") from e


def _convert_audio(input_file: Path, output_file: Path) -> None:
    subprocess.run(
        [resolve_ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_file), "-ar", "24000", "-ac", "1", str(output_file)],
        check=True,
    )


def _generate_alarm_fallback(output_file: Path) -> None:
    subprocess.run(
        [
            resolve_ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=850:duration=0.5",
            "-f", "lavfi", "-i", "sine=frequency=0:duration=0.2",
            "-f", "lavfi", "-i", "sine=frequency=850:duration=0.5",
            "-f", "lavfi", "-i", "sine=frequency=0:duration=0.2",
            "-f", "lavfi", "-i", "sine=frequency=850:duration=0.8",
            "-filter_complex", "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1",
            "-ar", "24000", "-ac", "1", str(output_file),
        ],
        check=True,
    )


def _concat_audio_files(input_files: list[Path], output_file: Path) -> None:
    labels = []
    filter_parts = []
    command = [resolve_ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error"]
    for idx, input_file in enumerate(input_files):
        command.extend(["-i", str(input_file)])
        label = f"a{idx}"
        labels.append(f"[{label}]")
        filter_parts.append(f"[{idx}:a]aresample=24000,aformat=channel_layouts=mono[{label}]")
    filter_complex = ";".join(filter_parts + [f"{''.join(labels)}concat=n={len(input_files)}:v=0:a=1[a]"])
    command.extend(["-filter_complex", filter_complex, "-map", "[a]", "-ar", "24000", "-ac", "1", str(output_file)])
    subprocess.run(command, check=True)


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
    if artifact_manifest.get("kind") in ("hourly_chime", "short_tts", "tts_audio", "breaking_news"):
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
    elif manifest.get("kind") in ("ai_music", "hourly_chime", "short_tts", "tts_audio", "breaking_news") and manifest.get("audio_file"):
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
