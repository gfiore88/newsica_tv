from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from newsica.config.paths import RUNTIME_DIR

TELEGRAM_VOICES_FILE = RUNTIME_DIR / "telegram_voices.json"


import os
from newsica.storage.repositories import telegram_repository

def list_voices() -> list[dict]:
    return telegram_repository.get_all_voices()

def enqueue_voice(
    *,
    author_username: str | None,
    author_first_name: str,
    file_id: str,
    duration: int,
    original_path: str,
    converted_path: str,
    status: str = "pending",
) -> dict:
    return telegram_repository.add_request(
        author_username=author_username,
        author_first_name=author_first_name,
        file_id=file_id,
        duration=duration,
        original_path=original_path,
        converted_path=converted_path,
        status=status
    )

def get_voice(voice_id: str) -> dict | None:
    return telegram_repository.get_voice_by_id(voice_id)

def update_voice(
    voice_id: str,
    **updates,
) -> dict | None:
    # Not used broadly anymore since we have specific methods
    # But if someone passes status we can use update_status
    if "status" in updates:
        return telegram_repository.update_status(voice_id, updates["status"])
    return None

def approve_voice(voice_id: str) -> dict | None:
    return telegram_repository.update_status(voice_id, "approved")

def reject_voice(voice_id: str) -> dict | None:
    voice = get_voice(voice_id)
    if voice:
        for key in ("original_path", "converted_path"):
            filepath = voice.get(key)
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    return telegram_repository.update_status(voice_id, "rejected")

def consume_next_approved_voice() -> dict | None:
    voices = telegram_repository.get_voices_by_status("approved")
    if voices:
        voice = voices[0]
        return telegram_repository.update_status(voice["id"], "queued_for_playout")
    return None

def mark_played(voice_id: str) -> dict | None:
    voice = get_voice(voice_id)
    if voice:
        for key in ("original_path", "converted_path"):
            filepath = voice.get(key)
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    return telegram_repository.update_status(voice_id, "played")
