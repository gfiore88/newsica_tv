from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path


class ArtifactValidationError(RuntimeError):
    pass


def runtime_assets_dir() -> Path:
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    override = os.getenv("NEWSICA_RUNTIME_ASSETS_DIR", "").strip()
    return Path(override) if override else base_dir / "runtime" / "assets"


def cleanup_incoming_artifacts(*, older_than_seconds: int, assets_dir: str | Path | None = None) -> int:
    root = Path(assets_dir) if assets_dir else runtime_assets_dir()
    incoming_root = root / "incoming"
    if not incoming_root.exists():
        return 0

    cutoff = time.time() - int(older_than_seconds)
    removed = 0
    for candidate in incoming_root.iterdir():
        if not candidate.is_dir():
            continue
        try:
            if candidate.stat().st_mtime < cutoff:
                shutil.rmtree(candidate)
                removed += 1
        except FileNotFoundError:
            continue
    return removed


def validate_slot_audio_artifact(incoming_dir: str | Path, expected: dict) -> dict:
    incoming_path = Path(incoming_dir)
    manifest_path = incoming_path / "manifest.json"
    if not manifest_path.exists():
        raise ArtifactValidationError(f"Missing manifest.json in {incoming_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ArtifactValidationError(f"Invalid manifest.json: {e}") from e

    for field in ("slot_time", "character", "title"):
        expected_value = expected.get(field)
        if expected_value and manifest.get(field) != expected_value:
            raise ArtifactValidationError(
                f"Manifest mismatch for {field}: expected {expected_value!r}, got {manifest.get(field)!r}"
            )

    audio_files = manifest.get("audio_files") or []
    if not audio_files:
        fallback = "audio.wav"
        if (incoming_path / fallback).exists():
            audio_files = [fallback]
        else:
            raise ArtifactValidationError("Manifest does not declare audio_files and audio.wav is missing")

    for relative_file in audio_files:
        candidate = incoming_path / str(relative_file)
        if not candidate.exists() or not candidate.is_file():
            raise ArtifactValidationError(f"Declared artifact file is missing: {relative_file}")

    return manifest


def publish_slot_audio_artifact(incoming_dir: str | Path, slot_time: str, *, assets_dir: str | Path | None = None) -> Path:
    incoming_path = Path(incoming_dir)
    slot_id = slot_time.replace(":", "")
    root = Path(assets_dir) if assets_dir else runtime_assets_dir()
    ready_root = root / "ready"
    archive_root = root / "archive"
    target = ready_root / slot_id
    staging_target = ready_root / f".{slot_id}.publishing"

    ready_root.mkdir(parents=True, exist_ok=True)
    archive_root.mkdir(parents=True, exist_ok=True)
    if staging_target.exists():
        shutil.rmtree(staging_target)
    shutil.copytree(incoming_path, staging_target)

    if target.exists():
        archived = archive_root / f"{slot_id}_replaced_{int(time.time())}"
        target.rename(archived)
    staging_target.rename(target)
    return target


def validate_ai_music_artifact(incoming_dir: str | Path) -> dict:
    incoming_path = Path(incoming_dir)
    manifest_path = incoming_path / "manifest.json"
    if not manifest_path.exists():
        raise ArtifactValidationError(f"Missing manifest.json in {incoming_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ArtifactValidationError(f"Invalid manifest.json: {e}") from e

    audio_file = manifest.get("audio_file") or manifest.get("file") or "audio.wav"
    candidate = incoming_path / Path(str(audio_file)).name
    if not candidate.exists() or not candidate.is_file():
        raise ArtifactValidationError(f"AI music artifact file is missing: {audio_file}")
    manifest["audio_file"] = candidate.name
    return manifest


def publish_ai_music_artifact(incoming_dir: str | Path, *, assets_dir: str | Path | None = None) -> Path:
    incoming_path = Path(incoming_dir)
    manifest = validate_ai_music_artifact(incoming_path)
    root = Path(assets_dir) if assets_dir else runtime_assets_dir()
    target_root = root / "ai_music"
    target_root.mkdir(parents=True, exist_ok=True)

    source_audio = incoming_path / manifest["audio_file"]
    target_audio = target_root / source_audio.name
    if target_audio.exists():
        stem = target_audio.stem
        suffix = target_audio.suffix
        target_audio = target_root / f"{stem}_{int(time.time())}{suffix}"
    shutil.copy2(source_audio, target_audio)

    manifest_copy = dict(manifest)
    manifest_copy["audio_file"] = target_audio.name
    manifest_copy["audio_path"] = str(target_audio)
    manifest_path = target_audio.with_suffix(target_audio.suffix + ".json")
    manifest_path.write_text(json.dumps(manifest_copy, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_audio
