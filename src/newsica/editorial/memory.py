import os
import json
import datetime
from newsica.config.paths import RUNTIME_DIR

MEMORY_FILE = os.path.join(RUNTIME_DIR, "editorial-memory.json")

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {
            "recent_titles": [],
            "recent_rubrics": [],
            "recent_music_tracks": [],
            "recent_music_titles": [],
            "last_intro_by_rubric": {}
        }
    try:
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
            # Assicuriamoci che tutti i campi siano presenti
            for key in ["recent_titles", "recent_rubrics", "recent_music_tracks", "recent_music_titles", "last_intro_by_rubric"]:
                if key not in data:
                    data[key] = [] if key != "last_intro_by_rubric" else {}
            return data
    except Exception as e:
        print(f"⚠️ Errore lettura MEMORY_FILE: {e}")
        return {
            "recent_titles": [],
            "recent_rubrics": [],
            "recent_music_tracks": [],
            "recent_music_titles": [],
            "last_intro_by_rubric": {}
        }

def save_memory(memory):
    try:
        temp_file = MEMORY_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(memory, f, indent=2)
        os.replace(temp_file, MEMORY_FILE)
    except Exception as e:
        print(f"⚠️ Errore salvataggio atomico MEMORY_FILE: {e}")

def add_title(title):
    mem = load_memory()
    if title not in mem["recent_titles"]:
        mem["recent_titles"].append(title)
        # Mantieni al massimo 30 titoli
        if len(mem["recent_titles"]) > 30:
            mem["recent_titles"].pop(0)
        save_memory(mem)

def add_rubric(rubric):
    mem = load_memory()
    mem["recent_rubrics"].append(rubric)
    if len(mem["recent_rubrics"]) > 10:
        mem["recent_rubrics"].pop(0)
    save_memory(mem)

def add_music_track(track):
    mem = load_memory()
    # Pulisci il nome del file dal percorso completo per coerenza
    track_name = os.path.basename(track)
    if track_name not in mem["recent_music_tracks"]:
        mem["recent_music_tracks"].append(track_name)
        if len(mem["recent_music_tracks"]) > 15:
            mem["recent_music_tracks"].pop(0)
        save_memory(mem)

def add_music_title(title):
    cleaned = " ".join((title or "").split())
    if not cleaned:
        return
    mem = load_memory()
    if cleaned not in mem["recent_music_titles"]:
        mem["recent_music_titles"].append(cleaned)
        if len(mem["recent_music_titles"]) > 20:
            mem["recent_music_titles"].pop(0)
        save_memory(mem)

def get_recent_music_titles(limit=8):
    mem = load_memory()
    titles = mem.get("recent_music_titles", [])
    return titles[-limit:]

def is_title_recent(title):
    mem = load_memory()
    return title in mem["recent_titles"]

def is_music_track_recent(track):
    mem = load_memory()
    track_name = os.path.basename(track)
    return track_name in mem["recent_music_tracks"]

def update_last_intro(rubric):
    mem = load_memory()
    mem["last_intro_by_rubric"][rubric] = datetime.datetime.now().isoformat()
    save_memory(mem)

def should_short_intro(rubric, threshold_seconds=7200):
    mem = load_memory()
    last_intro_str = mem["last_intro_by_rubric"].get(rubric)
    if not last_intro_str:
        return False
    try:
        last_intro = datetime.datetime.fromisoformat(last_intro_str)
        elapsed = (datetime.datetime.now() - last_intro).total_seconds()
        return elapsed < threshold_seconds
    except Exception:
        return False
