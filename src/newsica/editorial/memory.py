from __future__ import annotations

import json
from pathlib import Path

from newsica.storage.repositories.editorial_memory_repository import (
    add_music_title as _db_add_music_title,
)
from newsica.storage.repositories.editorial_memory_repository import (
    get_recent_music_titles as _db_get_recent_music_titles,
)

MEMORY_FILE = "deprecated"


def _use_legacy_file_storage() -> bool:
    return MEMORY_FILE != "deprecated"


def _load_legacy_memory() -> list[str]:
    memory_path = Path(MEMORY_FILE)
    if not memory_path.exists():
        return []
    try:
        payload = json.loads(memory_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _save_legacy_memory(entries: list[str]) -> None:
    memory_path = Path(MEMORY_FILE)
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def add_music_title(title: str) -> None:
    if _use_legacy_file_storage():
        entries = _load_legacy_memory()
        entries.append(title)
        _save_legacy_memory(entries)
        return
    _db_add_music_title(title)


def get_recent_music_titles(limit: int = 30) -> list[str]:
    if _use_legacy_file_storage():
        entries = _load_legacy_memory()
        if limit <= 0:
            return []
        return entries[-limit:]
    recent = _db_get_recent_music_titles(limit=limit)
    return list(reversed(recent))
