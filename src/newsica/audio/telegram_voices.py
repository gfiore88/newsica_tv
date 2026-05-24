from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from newsica.config.paths import RUNTIME_DIR

TELEGRAM_VOICES_FILE = RUNTIME_DIR / "telegram_voices.json"


def _load_payload(path: Path = TELEGRAM_VOICES_FILE) -> dict:
    if not path.exists():
        return {"voices": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"voices": []}
    if not isinstance(data, dict):
        return {"voices": []}
    voices = data.get("voices")
    if not isinstance(voices, list):
        data["voices"] = []
    return data


def _save_payload(payload: dict, path: Path = TELEGRAM_VOICES_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def list_voices(path: Path = TELEGRAM_VOICES_FILE) -> list[dict]:
    return list(_load_payload(path).get("voices", []))


def enqueue_voice(
    *,
    author_username: str | None,
    author_first_name: str,
    file_id: str,
    duration: int,
    original_path: str,
    converted_path: str,
    status: str = "pending",
    path: Path = TELEGRAM_VOICES_FILE,
) -> dict:
    payload = _load_payload(path)
    voice_id = f"tgvoice_{uuid.uuid4().hex[:12]}"
    voice = {
        "id": voice_id,
        "author_username": author_username or "",
        "author_first_name": author_first_name,
        "file_id": file_id,
        "duration": duration,
        "original_path": original_path,
        "converted_path": converted_path,
        "status": status,
        "received_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    payload["voices"].append(voice)
    _save_payload(payload, path)
    return voice


def get_voice(voice_id: str, path: Path = TELEGRAM_VOICES_FILE) -> dict | None:
    payload = _load_payload(path)
    for voice in payload.get("voices", []):
        if voice.get("id") == voice_id:
            return dict(voice)
    return None


def update_voice(
    voice_id: str,
    *,
    path: Path = TELEGRAM_VOICES_FILE,
    **updates,
) -> dict | None:
    payload = _load_payload(path)
    for voice in payload.get("voices", []):
        if voice.get("id") != voice_id:
            continue
        voice.update(updates)
        _save_payload(payload, path)
        return dict(voice)
    return None


def approve_voice(voice_id: str, path: Path = TELEGRAM_VOICES_FILE) -> dict | None:
    return update_voice(
        voice_id,
        path=path,
        status="approved",
        approved_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def reject_voice(voice_id: str, path: Path = TELEGRAM_VOICES_FILE) -> dict | None:
    # Recuperiamo il file per poterlo eliminare fisicamente
    voice = get_voice(voice_id, path)
    if voice:
        for key in ("original_path", "converted_path"):
            filepath = voice.get(key)
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    return update_voice(
        voice_id,
        path=path,
        status="rejected",
        rejected_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def consume_next_approved_voice(path: Path = TELEGRAM_VOICES_FILE) -> dict | None:
    payload = _load_payload(path)
    for voice in payload.get("voices", []):
        if voice.get("status") != "approved":
            continue
        voice["status"] = "queued_for_playout"
        voice["queued_for_playout_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_payload(payload, path)
        return dict(voice)
    return None


def mark_played(voice_id: str, path: Path = TELEGRAM_VOICES_FILE) -> dict | None:
    # Rimuoviamo il file originale e quello convertito dopo la riproduzione per non occupare spazio
    voice = get_voice(voice_id, path)
    if voice:
        for key in ("original_path", "converted_path"):
            filepath = voice.get(key)
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    return update_voice(
        voice_id,
        path=path,
        status="played",
        played_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
