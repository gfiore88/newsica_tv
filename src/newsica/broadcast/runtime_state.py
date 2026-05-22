import os
import json
import time
import tempfile
from newsica.config.paths import TMP_DIR, RUNTIME_DIR

STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")
PROGRAM_FILE = os.path.join(TMP_DIR, "current_program.txt")
NEXT_PROGRAM_FILE = os.path.join(TMP_DIR, "next_program.txt")

ACCENT_FILES = {
    "news": os.path.join(TMP_DIR, "accent_news.txt"),
    "sport": os.path.join(TMP_DIR, "accent_sport.txt"),
    "meteo": os.path.join(TMP_DIR, "accent_meteo.txt"),
    "wellness": os.path.join(TMP_DIR, "accent_wellness.txt"),
    "music_only": os.path.join(TMP_DIR, "accent_music.txt"),
    "breaking_news": os.path.join(TMP_DIR, "accent_breaking.txt"),
}

def ensure_folders():
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    if not os.path.exists(STATE_FILE):
        write_state_files({"status": "OFFLINE"})
    
    if not os.path.exists(PROGRAM_FILE):
        with open(PROGRAM_FILE, "w") as f:
            f.write("NEWSICA TV")
            
    if not os.path.exists(NEXT_PROGRAM_FILE):
        with open(NEXT_PROGRAM_FILE, "w") as f:
            f.write("A seguire: --")
            
    for accent_file in ACCENT_FILES.values():
        if not os.path.exists(accent_file):
            with open(accent_file, "w") as f:
                f.write("")

def write_accent_files(block_type):
    if block_type == "trasmissione_straordinaria":
        active_key = "breaking_news"
    else:
        active_key = block_type if block_type in ACCENT_FILES else "news"
    for key, accent_file in ACCENT_FILES.items():
        try:
            os.makedirs(os.path.dirname(accent_file), exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                dir=os.path.dirname(accent_file),
                prefix=os.path.basename(accent_file) + ".",
                suffix=".tmp",
                delete=False,
            ) as f:
                f.write(" " if key == active_key else "")
                temp_file = f.name
            os.replace(temp_file, accent_file)
        except Exception as e:
            print(f"⚠️ Errore scrittura accent file {key}: {e}")

def write_state_files(state):
    state = dict(state)
    state["last_update"] = state.get("last_update") or time.strftime("%Y-%m-%dT%H:%M:%S")
    current_segment = state.get("current_segment", "") or ""
    is_music_segment = (
        state.get("current_block") == "music_only"
        or current_segment == "music_rotation_until_deadline"
        or current_segment.startswith("music_")
    )
    if not is_music_segment:
        state.pop("current_music_title", None)
    
    # Scrittura atomica dello stato JSON
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            dir=os.path.dirname(STATE_FILE),
            prefix=os.path.basename(STATE_FILE) + ".",
            suffix=".tmp",
            delete=False,
        ) as sf:
            json.dump(state, sf, indent=2)
            temp_state = sf.name
        os.replace(temp_state, STATE_FILE)
    except Exception as e:
        print(f"⚠️ Errore scrittura atomica STATE_FILE: {e}")
        
    # Scrittura atomica di current_program.txt
    try:
        os.makedirs(os.path.dirname(PROGRAM_FILE), exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            dir=os.path.dirname(PROGRAM_FILE),
            prefix=os.path.basename(PROGRAM_FILE) + ".",
            suffix=".tmp",
            delete=False,
        ) as pf:
            pf.write(state.get("current_title", "").upper())
            temp_prog = pf.name
        os.replace(temp_prog, PROGRAM_FILE)
    except Exception as e:
        print(f"⚠️ Errore scrittura atomica PROGRAM_FILE: {e}")

    # Scrittura atomica di next_program.txt
    try:
        next_title = state.get("next_block", "")
        next_start = state.get("next_start")
        next_label = f"A seguire: {next_title}" if next_title else ""
        if next_label and next_start:
            next_label = f"{next_label} - {next_start}"
        os.makedirs(os.path.dirname(NEXT_PROGRAM_FILE), exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            dir=os.path.dirname(NEXT_PROGRAM_FILE),
            prefix=os.path.basename(NEXT_PROGRAM_FILE) + ".",
            suffix=".tmp",
            delete=False,
        ) as nf:
            nf.write(next_label)
            temp_next = nf.name
        os.replace(temp_next, NEXT_PROGRAM_FILE)
    except Exception as e:
        print(f"⚠️ Errore scrittura atomica NEXT_PROGRAM_FILE: {e}")
        
    write_accent_files(state.get("current_block", "news"))

def get_current_state():
    if not os.path.exists(STATE_FILE):
        return {"status": "OFFLINE"}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Errore lettura STATE_FILE: {e}")
        return {"status": "OFFLINE"}
