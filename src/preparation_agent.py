import time
import datetime
import shutil
import sys
import os
import fcntl
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

# Agents
from newsica.agents.content_strategist import ContentStrategistAgent
from newsica.agents.ai_integrator import AIIntegratorAgent
from newsica.agents.system_admin import SystemAdminAgent, ASSETS_DIR
from newsica.audio.ai_music_runtime import schedule_rotation_fill_job
from newsica.audio.music_library import DEFAULT_THEMED_MIN_TRACKS, MusicLibrary
from newsica.storage.repositories.ai_music_jobs_repository import count_active_jobs
from newsica.storage.repositories.shorts_plan_repository import (
    get_pending_generation_items,
    update_item_status,
)
from newsica.storage.repositories.shorts_library_repository import mark_short_social_posts

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
    schedule_data = get_current_schedule() or {}
    if not isinstance(schedule_data, dict):
        return []
    
    now = datetime.datetime.now()
    future_slots = []
    
    for slot_time, block_info in schedule_data.items():
        if not isinstance(block_info, dict):
            continue
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
    # Tutti i tipi di blocco, incluso music_only, ora vengono preparati (music_only riceve l'intro vocale)
    return True


def ensure_theme_music_ready(theme):
    normalized_theme = " ".join(str(theme or "").strip().lower().split())
    if not normalized_theme:
        return

    library = MusicLibrary()
    ready_count = library.count_ai_tracks_for_theme(normalized_theme)
    active_jobs = count_active_jobs(job_type="rotation_fill", theme=normalized_theme)
    missing = max(0, DEFAULT_THEMED_MIN_TRACKS - (ready_count + active_jobs))

    if missing <= 0:
        return

    for _ in range(missing):
        job, created = schedule_rotation_fill_job("preparation_agent", theme=normalized_theme)
        if created:
            print(
                f"🎸 [PreparationAgent] Accodato job musica tematica per theme='{normalized_theme}' "
                f"({ready_count} pronti, {active_jobs} attivi, target {DEFAULT_THEMED_MIN_TRACKS}) | job={job['id']}"
            )
            active_jobs += 1
        else:
            break

def run_loop():
    print("🚀 [PreparationAgent] Avviato in background. Orchestrazione multi-agente in corso...")
    
    strategist = ContentStrategistAgent()
    sysadmin = SystemAdminAgent()
    from newsica.agents.shorts_agent import ShortsAgent
    from newsica.utils.social_publisher import SocialPublisher
    shorts_agent = ShortsAgent()
    social_publisher = SocialPublisher()
    shorts_generation_lead_minutes = int(os.getenv("SHORTS_GENERATION_LEAD_MINUTES", "90"))

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

            try:
                from newsica.broadcast.runtime_state import get_current_state
                current_state = get_current_state() or {}
                if (
                    current_state.get("status") == "ON_AIR"
                    and current_state.get("current_block") == "music_only"
                    and current_state.get("theme")
                ):
                    ensure_theme_music_ready(current_state.get("theme"))
            except Exception as e:
                print(f"⚠️ [PreparationAgent] Errore controllo tema corrente live: {e}")

            # 2. Riconciliazione stato asset con il palinsesto corrente
            from schedule_generator import get_current_schedule
            schedule_data = get_current_schedule() or {}
            if not isinstance(schedule_data, dict):
                schedule_data = {}
            sysadmin.reconcile_asset_slots(schedule_data)

            # 3. Controllo palinsesto
            future_slots = get_future_slots(hours_ahead=2)
            
            for slot_time, block_info in future_slots:
                if not isinstance(block_info, dict):
                    continue
                character = block_info.get("type", "news")
                title = block_info.get("title", "")
                
                if is_complex_block(character):
                    theme = block_info.get("theme")
                    if character == "music_only" and theme:
                        ensure_theme_music_ready(theme)

                    # Richiediamo lo spazio di lavoro al SysAdmin
                    preparing_dir, status = sysadmin.prepare_slot(slot_time, character=character, title=title)
                    if not preparing_dir:
                        # Asset già pronto o in preparazione
                        continue
                        
                    print(f"🎬 [PreparationAgent] Orchestrazione per slot {slot_time} ({character})")
                    try:
                        # Fase 1: Strategia e Contenuto
                        content_data = strategist.prepare_content(character, title, theme=theme)
                        
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

            # 4. Esecuzione autonoma piano shorts giornaliero (1 item per ciclo)
            for item in get_pending_generation_items(limit=1, due_within_minutes=shorts_generation_lead_minutes):
                item_id = int(item.get("id", 0))
                mode = str(item.get("mode", "news")).strip().lower() or "news"
                due_at_by_platform = item.get("scheduled_for") or {}
                if not item_id:
                    continue
                update_item_status(item_id, "generating")
                try:
                    result = shorts_agent.run(mode=mode)
                    if result.get("status") != "success":
                        update_item_status(item_id, "failed", error=result.get("message", "generazione short fallita"))
                        continue

                    output_file = result.get("output", "")
                    filename = os.path.basename(output_file) if output_file else ""
                    title = result.get("news_title", "Short NewsicaTV")
                    caption = result.get("caption", "")
                    hashtags = result.get("hashtags") or []
                    full_caption = f"{caption}\n\n{' '.join(hashtags)}" if hashtags else caption

                    scheduled = social_publisher.schedule_to_all_socials(
                        video_path=output_file,
                        title=title,
                        caption=full_caption,
                        due_at_by_platform=due_at_by_platform,
                    )
                    if scheduled.get("status") in {"success", "partial"}:
                        platform_results = scheduled.get("results")
                        if isinstance(platform_results, dict):
                            mark_short_social_posts(filename, platform_results)
                        update_item_status(
                            item_id,
                            "scheduled",
                            short_filename=filename,
                            publish_result_json=json.dumps(scheduled, ensure_ascii=False),
                        )
                    else:
                        update_item_status(
                            item_id,
                            "failed",
                            short_filename=filename,
                            error=scheduled.get("message", "schedulazione social fallita"),
                            publish_result_json=json.dumps(scheduled, ensure_ascii=False),
                        )
                except Exception as e:
                    update_item_status(item_id, "failed", error=str(e))
                        
        except Exception as e:
            print(f"⚠️ [PreparationAgent] Errore critico nel loop: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    if not check_singleton("preparation_agent"):
        sys.exit(1)
    run_loop()
