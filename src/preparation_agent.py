import time
import datetime
import shutil
import sys
import os
import fcntl
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

# Agents
from newsica.agents.content_strategist import ContentStrategistAgent
from newsica.agents.ai_integrator import AIIntegratorAgent
from newsica.agents.system_admin import SystemAdminAgent, ASSETS_DIR

RUNTIME_DIR = BASE_DIR / "runtime"
_singleton_lock = None


def check_singleton(name):
    lock_file_path = RUNTIME_DIR / f"{name}.lock"
    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        global _singleton_lock
        _singleton_lock = f
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
        return True
    except Exception:
        print(f"❌ ERRORE: Un'altra istanza di {name} è già in esecuzione!")
        return False

def get_future_slots(hours_ahead=2, current_grace_minutes=30):
    # Leggiamo lo schedule
    from schedule_generator import get_current_schedule
    schedule_data = get_current_schedule()
    
    now = datetime.datetime.now()
    future_slots = []
    
    for slot_time, block_info in schedule_data.items():
        try:
            hour, minute = map(int, slot_time.split(":"))
            slot_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if slot_dt < now:
                elapsed = (now - slot_dt).total_seconds()
                if elapsed <= current_grace_minutes * 60:
                    slot_dt = now
                elif now.hour >= 22 and hour <= 2:
                    slot_dt += datetime.timedelta(days=1)
                else:
                    continue
                    
            delta = (slot_dt - now).total_seconds()
            if 0 <= delta <= (hours_ahead * 3600):
                future_slots.append((slot_time, block_info))
        except Exception:
            continue
            
    return sorted(future_slots, key=lambda x: x[0])

def is_complex_block(character):
    return character not in ["music_only"]

def run_loop():
    print("🚀 [PreparationAgent] Avviato in background. Orchestrazione multi-agente in corso...")
    
    strategist = ContentStrategistAgent()
    sysadmin = SystemAdminAgent()

    # Al boot: puliamo le cartelle "preparing" orfane, MA preserviamo quelle
    # per slot futuri validi con generazione in corso (es. podcast già a metà Chatterbox).
    # Regola: rimuoviamo solo se lo slot è passato o la cartella è vuota/stale.
    from schedule_generator import get_current_schedule
    now_boot = datetime.datetime.now()
    try:
        boot_schedule = get_current_schedule()
    except Exception:
        boot_schedule = {}

    preparing_root = ASSETS_DIR / "preparing"
    if preparing_root.exists():
        for p_dir in preparing_root.iterdir():
            if not p_dir.is_dir():
                continue
            slot_id = p_dir.name  # es. "1430"
            try:
                slot_time_str = f"{slot_id[:2]}:{slot_id[2:]}" if len(slot_id) == 4 else ""
            except Exception:
                slot_time_str = ""

            # Controlliamo se lo slot è futuro (o in grace da 30 min) nel palinsesto corrente
            is_future_valid = False
            if slot_time_str and slot_time_str in boot_schedule:
                try:
                    h, m = map(int, slot_time_str.split(":"))
                    slot_dt = now_boot.replace(hour=h, minute=m, second=0, microsecond=0)
                    elapsed = (now_boot - slot_dt).total_seconds()
                    if slot_dt >= now_boot or elapsed <= 30 * 60:
                        # Verifica che non sia stale (vuota o vecchissima)
                        age_sec = now_boot.timestamp() - p_dir.stat().st_mtime
                        is_empty = not any(p_dir.iterdir())
                        is_stale = is_empty or age_sec > SystemAdminAgent.STALE_PREPARING_SECONDS
                        if not is_stale:
                            print(
                                f"⏭️ [PreparationAgent] Conservo preparing/{p_dir.name}: "
                                f"slot futuro {slot_time_str} con generazione in corso "
                                f"(età {int(age_sec/60)} min)."
                            )
                            is_future_valid = True
                except Exception:
                    pass

            if not is_future_valid:
                try:
                    shutil.rmtree(p_dir)
                    print(f"🧹 [PreparationAgent] Pulito residuo orfano al boot: {p_dir.name}")
                except Exception as e:
                    print(f"⚠️ Errore pulizia residuo {p_dir.name}: {e}")


    while True:
        try:
            # 1. Manutenzione di sistema
            sysadmin.cleanup_old_assets(max_age_hours=24)

            # 2. Riconciliazione stato asset con il palinsesto corrente
            from schedule_generator import get_current_schedule
            schedule_data = get_current_schedule()
            sysadmin.reconcile_asset_slots(schedule_data)

            # 3. Controllo palinsesto
            future_slots = get_future_slots(hours_ahead=2)
            
            for slot_time, block_info in future_slots:
                character = block_info.get("type", "news")
                title = block_info.get("title", "")
                
                if is_complex_block(character):
                    # Richiediamo lo spazio di lavoro al SysAdmin
                    preparing_dir, status = sysadmin.prepare_slot(slot_time, character=character, title=title)
                    if not preparing_dir:
                        # Asset già pronto o in preparazione
                        continue
                        
                    print(f"🎬 [PreparationAgent] Orchestrazione per slot {slot_time} ({character})")
                    try:
                        # Fase 1: Strategia e Contenuto
                        content_data = strategist.prepare_content(character, title)
                        
                        # Fase 2: Integrazione AI (LLM -> TTS -> Audio) - Usiamo la cartella di preparazione isolata
                        slot_integrator = AIIntegratorAgent(work_dir=preparing_dir)
                        script_text = slot_integrator.generate_script(content_data)
                        audio_files = slot_integrator.generate_audio(script_text, content_data)
                        
                        if not audio_files:
                            raise RuntimeError("Nessun file audio prodotto dall'Integrator.")
                            
                        # Fase 3: Consegna e Commit
                        sysadmin.commit_assets(
                            slot_time,
                            audio_files,
                            preparing_dir,
                            metadata={
                                "slot_time": slot_time,
                                "character": character,
                                "title": content_data.get("title", title),
                                "prepared_at": datetime.datetime.now().isoformat(timespec="seconds"),
                            },
                        )
                        
                    except Exception as e:
                        sysadmin.fail_slot(slot_time, preparing_dir, error=str(e))
                        
        except Exception as e:
            print(f"⚠️ [PreparationAgent] Errore critico nel loop: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    if not check_singleton("preparation_agent"):
        sys.exit(1)
    run_loop()
