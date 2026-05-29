from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


GENERATION_MODE_ENV = "NEWSICA_GENERATION_MODE"
LOCAL_MODE = "local"
REMOTE_MODE = "remote"
SUPPORTED_MODES = {LOCAL_MODE, REMOTE_MODE}


class GenerationModeError(RuntimeError):
    pass


class GenerationDeferred(RuntimeError):
    def __init__(self, job: dict):
        self.job = job
        super().__init__(f"Generation deferred to remote job {job.get('id')}")


@dataclass(frozen=True)
class GenerationResult:
    audio_files: list[Path]
    script_text: str


class GenerationClient(Protocol):
    mode: str

    def generate_slot_audio(self, content_data: dict, work_dir: str | Path) -> GenerationResult:
        ...

    def schedule_ai_music(self, source: str, *, theme: str | None = None) -> tuple[dict, bool]:
        ...


class LocalGenerationClient:
    mode = LOCAL_MODE

    def generate_slot_audio(self, content_data: dict, work_dir: str | Path) -> GenerationResult:
        from newsica.agents.ai_integrator import AIIntegratorAgent
        
        integrator = AIIntegratorAgent(work_dir=Path(work_dir))
        audio_files = []
        script_texts = []
        
        if content_data.get("with_meteo_intro"):
            from newsica.agents.content_strategist import ContentStrategistAgent
            strategist = ContentStrategistAgent()
            meteo_data = strategist.prepare_content("meteo", "Meteo Flash")
            meteo_script = integrator.generate_script(meteo_data)
            integrator.generate_audio(meteo_script, meteo_data)
            
            # Rinomina l'audio del meteo per non sovrascrivere lo show principale
            meteo_file = Path(work_dir) / "meteo.wav"
            if (Path(work_dir) / "audio.wav").exists():
                (Path(work_dir) / "audio.wav").rename(meteo_file)
                audio_files.append(meteo_file)
            script_texts.append("--- METEO ---\n" + meteo_script)

        script_text = integrator.generate_script(content_data)
        main_audio_files = integrator.generate_audio(script_text, content_data)
        audio_files.extend(list(main_audio_files))
        script_texts.append("--- SHOW PRINCIPALE ---\n" + script_text)
        
        return GenerationResult(audio_files=audio_files, script_text="\n\n".join(script_texts))

    def schedule_ai_music(self, source: str, *, theme: str | None = None) -> tuple[dict, bool]:
        from newsica.audio.ai_music_runtime import schedule_rotation_fill_job

        return schedule_rotation_fill_job(source, theme=theme)


class RemoteGenerationClient:
    mode = REMOTE_MODE

    def __init__(self) -> None:
        self.worker_queue = os.getenv("NEWSICA_REMOTE_GENERATION_QUEUE", "sqlite").strip().lower()
        if self.worker_queue != "sqlite":
            self.endpoint = _required_env("NEWSICA_REMOTE_GENERATION_URL")
            self.token = _required_env("NEWSICA_REMOTE_GENERATION_TOKEN")

    def generate_slot_audio(self, content_data: dict, work_dir: str | Path) -> GenerationResult:
        from newsica.storage.repositories.generation_jobs_repository import enqueue_job

        slot_time = str(content_data.get("slot_time") or "").strip() or None
        character = str(content_data.get("character_id") or content_data.get("character") or "").strip() or None
        title = str(content_data.get("title") or "").strip() or None
        theme = str(content_data.get("theme") or "").strip() or None
        dedupe_key = _dedupe_key("slot_audio", slot_time, character, title)
        job, _created = enqueue_job(
            "slot_audio",
            priority=100,
            slot_time=slot_time,
            character=character,
            title=title,
            theme=theme,
            source="preparation_agent",
            dedupe_key=dedupe_key,
            payload={
                "content_data": content_data,
                "target_work_dir": str(Path(work_dir)),
            },
        )
        raise GenerationDeferred(job)

    def schedule_ai_music(self, source: str, *, theme: str | None = None) -> tuple[dict, bool]:
        from newsica.storage.repositories.generation_jobs_repository import enqueue_job

        normalized_theme = " ".join(str(theme or "").strip().lower().split()) or None
        dedupe_key = "ai_music:rotation_fill" if normalized_theme is None else f"ai_music:rotation_fill:{normalized_theme}"
        return enqueue_job(
            "ai_music",
            priority=20,
            theme=normalized_theme,
            source=source,
            dedupe_key=dedupe_key,
            payload={
                "source": source,
                "theme": normalized_theme,
                "job_type": "rotation_fill",
            },
        )


def get_generation_mode(env: dict[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    mode = source.get(GENERATION_MODE_ENV, LOCAL_MODE).strip().lower()
    if not mode:
        return LOCAL_MODE
    if mode not in SUPPORTED_MODES:
        raise GenerationModeError(
            f"Unsupported {GENERATION_MODE_ENV}={mode!r}. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_MODES))}."
        )
    return mode


def get_generation_client(mode: str | None = None) -> GenerationClient:
    resolved_mode = (mode or get_generation_mode()).strip().lower()
    if resolved_mode == LOCAL_MODE:
        return LocalGenerationClient()
    if resolved_mode == REMOTE_MODE:
        return RemoteGenerationClient()
    raise GenerationModeError(
        f"Unsupported generation mode {resolved_mode!r}. "
        f"Expected one of: {', '.join(sorted(SUPPORTED_MODES))}."
    )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise GenerationModeError(
            f"{name} must be configured in the environment for remote generation. "
            "Do not hardcode VPS URLs, tokens, paths, usernames or credentials in code."
        )
    return value


def _dedupe_key(*parts: object) -> str:
    return ":".join(str(part or "").strip().lower().replace(" ", "_") for part in parts)
