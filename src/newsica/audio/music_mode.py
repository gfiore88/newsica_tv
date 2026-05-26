from __future__ import annotations

from newsica.storage.repositories.editorial_memory_repository import get_memory, set_memory

MUSIC_MODE_MIXED = "mixed"
MUSIC_MODE_AI_ONLY = "ai_only"
VALID_MUSIC_MODES = {MUSIC_MODE_MIXED, MUSIC_MODE_AI_ONLY}
DEFAULT_MUSIC_MODE = MUSIC_MODE_MIXED

def normalize_music_mode(mode: str | None) -> str:
    if mode in VALID_MUSIC_MODES:
        return mode
    return DEFAULT_MUSIC_MODE

def read_music_mode() -> str:
    try:
        data = get_memory("music_mode")
        if data:
            return normalize_music_mode(data)
        return DEFAULT_MUSIC_MODE
    except Exception:
        return DEFAULT_MUSIC_MODE

def write_music_mode(mode: str) -> str:
    normalized = normalize_music_mode(mode)
    try:
        set_memory("music_mode", normalized)
    except Exception as e:
        print(f"⚠️ Errore db in write_music_mode: {e}")
    return normalized
