import sys
import os
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from newsica.agents.editorial_director import EditorialDirectorAgent
from newsica.storage.repositories.schedule_repository import get_schedule, save_schedule

def generate_schedule(target_date=None, force=False):
    """
    Genera un palinsesto tramite l'EditorialDirectorAgent e lo salva nel database.
    Se esiste già e non c'è force=True, non fa nulla.
    """
    if not target_date:
        target_date = datetime.date.today().isoformat()
        
    existing = get_schedule(target_date)
    if existing and not force:
        print(f"✅ Palinsesto per {target_date} già esistente in DB. Usa force=True per sovrascrivere.")
        return existing
        
    print(f"🎬 Generazione nuovo palinsesto per {target_date}...")
    agent = EditorialDirectorAgent()
    schedule_data = agent.generate_dynamic_schedule()
    
    save_schedule(target_date, schedule_data)
    
    print(f"✅ Palinsesto salvato nel database per {target_date}.")
    return schedule_data

def get_current_schedule(target_date=None):
    """
    Ritorna il palinsesto del giorno (dal DB). Se non esiste, lo genera.
    """
    if not target_date:
        target_date = datetime.date.today().isoformat()
        
    sched = get_schedule(target_date)
    if sched:
        return sched
        
    # Se non esiste, generiamolo
    return generate_schedule(target_date)

if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    sched = generate_schedule(force=force_flag)
    print("Palinsesto risultante:")
    print(sched)
