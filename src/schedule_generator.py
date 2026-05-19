import json
import os
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")

# Palinsesto editoriale base (Fase 2 - Content Strategist)
DEFAULT_SCHEDULE = {
    "00:00": {"title": "Newsica Night", "type": "music_only"},
    "06:00": {"title": "Morning News", "type": "news"},
    "08:00": {"title": "Sport Flash", "type": "sport"},
    "09:00": {"title": "Wellness Time", "type": "wellness"},
    "10:00": {"title": "Meteo Update", "type": "meteo"},
    "12:00": {"title": "Pranzo News", "type": "news"},
    "14:00": {"title": "Pomeriggio Sport", "type": "sport"},
    "16:00": {"title": "Pausa Wellness", "type": "wellness"},
    "18:00": {"title": "Riepilogo Giornata", "type": "news"},
    "20:00": {"title": "Newsica Sera", "type": "news"},
    "22:00": {"title": "Meteo Notte", "type": "meteo"}
}

def generate_schedule(target_date=None):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    if not target_date:
        target_date = date.today().isoformat()
    
    file_path = os.path.join(RUNTIME_DIR, f"schedule_{target_date}.json")
    with open(file_path, "w") as f:
        json.dump(DEFAULT_SCHEDULE, f, indent=2)
        
    print(f"✅ Palinsesto generato per {target_date} in {file_path}")
    return file_path

def get_current_schedule():
    target_date = date.today().isoformat()
    file_path = os.path.join(RUNTIME_DIR, f"schedule_{target_date}.json")
    if not os.path.exists(file_path):
        generate_schedule(target_date)
        
    with open(file_path, "r") as f:
        return json.load(f)

if __name__ == "__main__":
    generate_schedule()
