import json
import os
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")

def generate_schedule(target_date=None):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    if not target_date:
        target_date = date.today().isoformat()
    
    file_path = os.path.join(RUNTIME_DIR, f"schedule_{target_date}.json")
    
    # Import the Editorial Director Agent
    try:
        import sys
        src_dir = os.path.join(BASE_DIR, "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
            
        from newsica.agents.editorial_director import EditorialDirectorAgent
        agent = EditorialDirectorAgent()
        schedule_data = agent.generate_dynamic_schedule()
    except Exception as e:
        print(f"⚠️ Errore caricamento EditorialDirectorAgent: {e}")
        # Fallback ultra base
        schedule_data = {
            "00:00": {"title": "Newsica Night", "type": "music_only"},
            "06:00": {"title": "Morning News", "type": "news"},
            "12:00": {"title": "Pranzo News", "type": "news"},
            "20:00": {"title": "Newsica Sera", "type": "news"}
        }

    with open(file_path, "w") as f:
        json.dump(schedule_data, f, indent=2)
        
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
