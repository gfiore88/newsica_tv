import os
import json
import datetime
from newsica.config.paths import RUNTIME_DIR

MEMORY_FILE = os.path.join(RUNTIME_DIR, "editorial-memory.json")

import os
import datetime
from newsica.storage.repositories import editorial_memory_repository

def load_memory():
    # Legacy wrapper if any old code still calls it
    # We shouldn't need it, but we'll return a dynamic struct to avoid crashing
    return {
        "recent_titles": editorial_memory_repository.get_recent_memories("title", 30),
        "recent_rubrics": editorial_memory_repository.get_recent_memories("rubric", 10),
        "recent_music_tracks": editorial_memory_repository.get_recent_memories("music_track", 15),
        "recent_music_titles": editorial_memory_repository.get_recent_memories("music_title", 20),
        "last_intro_by_rubric": {}
    }

def save_memory(memory):
    # No-op in SQLite version
    pass

def add_title(title):
    recent = editorial_memory_repository.get_recent_memories("title", 30)
    if title not in recent:
        editorial_memory_repository.insert_memory("title", title)

def add_rubric(rubric):
    editorial_memory_repository.insert_memory("rubric", rubric)

def add_music_track(track):
    track_name = os.path.basename(track)
    recent = editorial_memory_repository.get_recent_memories("music_track", 15)
    if track_name not in recent:
        editorial_memory_repository.insert_memory("music_track", track_name)

def add_music_title(title):
    cleaned = " ".join((title or "").split())
    if not cleaned:
        return
    recent = editorial_memory_repository.get_recent_memories("music_title", 20)
    if cleaned not in recent:
        editorial_memory_repository.insert_memory("music_title", cleaned)

def get_recent_music_titles(limit=8):
    return editorial_memory_repository.get_recent_memories("music_title", limit)

def is_title_recent(title):
    recent = editorial_memory_repository.get_recent_memories("title", 30)
    return title in recent

def is_music_track_recent(track):
    track_name = os.path.basename(track)
    recent = editorial_memory_repository.get_recent_memories("music_track", 15)
    return track_name in recent

def update_last_intro(rubric):
    editorial_memory_repository.insert_memory("last_intro", "intro", metadata=rubric)

def should_short_intro(rubric, threshold_seconds=7200):
    last_intro_str = editorial_memory_repository.get_last_intro_time(rubric)
    if not last_intro_str:
        return False
    try:
        last_intro = datetime.datetime.fromisoformat(last_intro_str)
        elapsed = (datetime.datetime.now() - last_intro).total_seconds()
        return elapsed < threshold_seconds
    except Exception:
        return False
