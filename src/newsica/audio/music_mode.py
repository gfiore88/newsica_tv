from __future__ import annotations

import json
from pathlib import Path

from newsica.config.paths import RUNTIME_DIR

MUSIC_MODE_FILE = RUNTIME_DIR / "music-mode.json"
MUSIC_MODE_MIXED = "mixed"
MUSIC_MODE_AI_ONLY = "ai_only"
VALID_MUSIC_MODES = {MUSIC_MODE_MIXED, MUSIC_MODE_AI_ONLY}
DEFAULT_MUSIC_MODE = MUSIC_MODE_MIXED


def normalize_music_mode(mode: str | None) -> str:
    if mode in VALID_MUSIC_MODES:
        return mode
    return DEFAULT_MUSIC_MODE


def read_music_mode(path: Path = MUSIC_MODE_FILE) -> str:
    try:
        if not path.exists():
            return DEFAULT_MUSIC_MODE
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return normalize_music_mode(data.get("mode"))
    except Exception:
        return DEFAULT_MUSIC_MODE


def write_music_mode(mode: str, path: Path = MUSIC_MODE_FILE) -> str:
    normalized = normalize_music_mode(mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"mode": normalized}
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    tmp_path.replace(path)
    return normalized
