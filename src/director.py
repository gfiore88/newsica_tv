import os
import time
import subprocess
import sys
import threading
import queue
import json
import datetime
from newsica.audio.jingles import get_jingle_for_block, CLASSIC_JINGLE_FILE
from newsica.audio.playout import AudioPlayout
from newsica.audio.settings import PCM_CHANNELS, PCM_CHUNK_BYTES, PCM_SAMPLE_RATE, resolve_ffmpeg_cmd
from newsica.domain.characters import get_character
from newsica.broadcast.scheduler import (
    get_current_block_info,
    get_next_block_info_for_key,
    schedule_deadline,
    get_wallclock_schedule_key
)
from newsica.broadcast.runtime_state import (
    ensure_folders,
    get_current_state,
    write_state_files,
    write_accent_files,
    STATE_FILE,
    PROGRAM_FILE,
    NEXT_PROGRAM_FILE
)
from newsica.broadcast.director_agent import DirectorAgent

# Custom print con timestamp per i log della regia
_original_print = print
def print(*args, **kwargs):
    now = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    if args:
        _original_print(f"{now} {args[0]}", *args[1:], **kwargs)
    else:
        _original_print(now, **kwargs)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
AUDIO_PIPE = os.path.join(TMP_DIR, "audio_pipe")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
CHIME_AUDIO_FILE = os.path.join(TMP_DIR, "hourly_chime.wav")

PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python3")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = sys.executable

# Coda audio con buffer limitato a ~17 secondi (200 chunk × 4096 byte × 1/24000 Hz)
# Era 5000 (>7 minuti) — causava saturazione pre-FFmpeg e deadlock sull'encoder H.264
audio_queue = queue.Queue(maxsize=200)
manual_block_override_index = None
current_active_index = 0
breaking_news_active = False
schedule_interrupt_event = threading.Event()
# Evento che segnala quando la FIFO è aperta in scrittura (FFmpeg collegato)
# Il generator_worker lo aspetta per evitare di pre-caricare audio prima del tempo
fifo_connected_event = threading.Event()

playout = AudioPlayout(
    audio_queue,
    schedule_interrupt_event,
    lambda: breaking_news_active,
)
FFMPEG_CMD = resolve_ffmpeg_cmd()
director_agent = DirectorAgent(playout)

def add_rubric_intro_to_script(title, character):
    script_file = os.path.join(TMP_DIR, "script.txt")
    if not os.path.exists(script_file):
        return
    intro = get_character(character).render_intro(title)
    with open(script_file, "r", encoding="utf-8") as f:
        script = f.read().strip()
    if script.startswith(intro):
        return
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(f"{intro}\n\n{script}")

def run_pipeline(character="news", title=None):
    print(f"\n--- 🔄 Avvio ciclo di aggiornamento news ({character}) ---")
    print("Scraping news...")
    subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "scraper.py")], check=True)
    print("Elaborazione testo (LLM)...")
    subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "llm_processor.py"), character], check=True)
    if title:
        add_rubric_intro_to_script(title, character)
    print("Sintesi vocale (TTS)...")
    subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "tts_generator.py"), character], check=True)

def generator_worker():
    global breaking_news_active, manual_block_override_index
    print("🤖 Thread Generatore (DirectorAgent Event Loop) avviato.")
    
    # Aspetta che la FIFO sia aperta da FFmpeg prima di pre-caricare audio.
    # Senza questo wait, mix_and_queue() riempirebbe la coda (200 chunk) in <0.1s
    # e il director scriverebbe troppo veloce prima che FFmpeg finisca l'handshake RTMP.
    print("⏸️  Generator in attesa che FFmpeg apra la pipe audio...")
    fifo_connected_event.wait()
    print("▶️  Generator sbloccato — avvio ciclo palinsesto.")
    
    while True:
        try:
            while breaking_news_active:
                time.sleep(1)
                
            schedule_interrupt_event.clear()
            action_info = director_agent.decide_next_action()
            action = action_info.get("action")
            
            if action == "PLAY_JINGLE":
                jingle_file = action_info["file"]
                label = action_info["label"]
                next_segment = action_info.get("next_segment")
                
                playout.queue_jingle(jingle_file, label)
                
                state = get_current_state()
                if state.get("status") != "OFFLINE":
                    state["current_segment"] = next_segment
                    write_state_files(state)
                    
            elif action == "PLAY_VOICE_MIX":
                voice_file = action_info["voice_file"]
                music_file = action_info["music_file"]
                char = action_info["character"]
                title = action_info["title"]
                seg = action_info["segment"]
                
                block_info = {
                    "status": "ON_AIR",
                    "current_block": char,
                    "current_title": f"{title} - {seg}",
                    "next_block": get_current_state().get("next_block", ""),
                    "next_start": get_current_state().get("next_start", ""),
                    "scheduled_slot": get_current_state().get("scheduled_slot", ""),
                    "breaking_news_available": False
                }
                
                if music_file:
                    playout.mix_and_queue(music_file, voice_file, block_info)
                else:
                    playout.queue_pcm_from_file(voice_file, block_info)
                    
            elif action == "PLAY_VOICE":
                voice_file = action_info["file"]
                char = action_info["character"]
                title = action_info["title"]
                seg = action_info["segment"]
                
                block_info = {
                    "status": "ON_AIR",
                    "current_block": char,
                    "current_title": f"{title} - {seg}",
                    "next_block": get_current_state().get("next_block", ""),
                    "next_start": get_current_state().get("next_start", ""),
                    "scheduled_slot": get_current_state().get("scheduled_slot", ""),
                    "breaking_news_available": False
                }
                playout.queue_pcm_from_file(voice_file, block_info)
                
            elif action == "PLAY_MUSIC":
                music_file = action_info["file"]
                label = action_info["label"]
                playout.queue_single_music_track(music_file)
                
            elif action == "WAIT_OR_GENERATE":
                char = action_info["character"]
                title = action_info["title"]
                time_key = action_info["time_key"]
                next_segment = action_info.get("next_segment", "intro")
                
                print(f"🚀 Genero blocco in background: {title} ({char})")
                run_pipeline(char, title)
                
                state = get_current_state()
                state["current_segment"] = next_segment
                write_state_files(state)
                
            elif action == "TRIGGER_NEXT_BLOCK":
                manual_block_override_index = None
                schedule_interrupt_event.set()
                playout.stop_current_process("⏰ Termino il blocco corrente per cambio fascia.")
                playout.clear_queue()
                write_state_files({"status": "OFFLINE"})
                
            elif action == "PLAY_SILENCE_FALLBACK":
                time.sleep(action_info.get("seconds", 2))
                
        except Exception as e:
            print(f"💥 Errore nel ciclo del generatore DirectorAgent: {e}")
            time.sleep(5)

def apply_preventive_fade_out_and_write(fifo_fd):
    import numpy as np
    chunks = []
    while len(chunks) < 10:
        try:
            item = audio_queue.get_nowait()
            if isinstance(item, dict) and item.get("type") == "metadata":
                audio_queue.task_done()
                continue
            data = item["data"] if isinstance(item, dict) else item
            chunks.append(data)
            audio_queue.task_done()
        except queue.Empty:
            break
            
    if not chunks:
        return
        
    num_chunks = len(chunks)
    for idx in range(num_chunks):
        data = chunks[idx]
        samples = np.frombuffer(data, dtype=np.int16).copy()
        start_factor = (num_chunks - idx) / num_chunks
        end_factor = (num_chunks - idx - 1) / num_chunks
        factors = np.linspace(start_factor, end_factor, len(samples))
        faded_data = (samples * factors).astype(np.int16).tobytes()
        try:
            write_fifo_chunk(fifo_fd, faded_data)
        except BrokenPipeError:
            raise

def write_fifo_chunk(fifo_fd, data, blocking=True):
    view = memoryview(data)
    written_total = 0
    while written_total < len(view):
        try:
            written = os.write(fifo_fd, view[written_total:])
            if written == 0:
                raise BrokenPipeError
            written_total += written
        except BlockingIOError:
            if not blocking:
                return False
            time.sleep(0.02)
    return True

def restore_after_interrupt(prev_state, label):
    state = prev_state if prev_state and prev_state.get("current_block") not in {"chime", "breaking_news"} else get_current_state()
    try:
        write_state_files(state)
    except Exception as e:
        print(f"⚠️ Errore ripristino stato dopo {label}: {e}")

def check_singleton(name):
    import fcntl
    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")
    def _try_acquire():
        f = open(lock_file_path, "r+") if os.path.exists(lock_file_path) else open(lock_file_path, "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            global _singleton_lock
            _singleton_lock = f
            f.seek(0)
            f.truncate()
            f.write(str(os.getpid()))
            f.flush()
            return True
        except (IOError, OSError):
            f.close()
            return False

    if _try_acquire():
        return True
    try:
        with open(lock_file_path, "r") as rf:
            content = rf.read().strip()
        if content:
            existing_pid = int(content)
            try:
                os.kill(existing_pid, 0)
                print(f"❌ ERRORE: Un'altra istanza di {name} è già in esecuzione! (PID {existing_pid})")
                return False
            except ProcessLookupError:
                print(f"⚠️ Lock stale rilevato (PID {existing_pid} non è più in vita). Rimozione e riavvio.")
                os.remove(lock_file_path)
                return _try_acquire()
    except Exception as e:
        print(f"⚠️ Impossibile leggere il lock: {e}. Rimozione e riavvio.")
        try:
            os.remove(lock_file_path)
        except Exception:
            pass
        return _try_acquire()
    return False

def main():
    global manual_block_override_index, current_active_index, breaking_news_active
    ensure_folders()
    if not check_singleton("director"):
        sys.exit(1)
    
    print("🎬 Regia NewsicaTV avviata.")
    write_state_files({"status": "OFFLINE"})
    
    threading.Thread(target=generator_worker, daemon=True).start()
    threading.Thread(target=lambda: subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "ticker_agent.py")]), daemon=True).start()
    threading.Thread(target=lambda: subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "hourly_chime_agent.py")]), daemon=True).start()
    
    silence = b'\x00' * PCM_CHUNK_BYTES
    last_schedule_key = get_wallclock_schedule_key()
    
    while True:
        print("\n📡 In attesa che FFmpeg si colleghi alla pipe in lettura...")
        fifo_fd = None
        try:
            fifo_fd = os.open(AUDIO_PIPE, os.O_WRONLY | os.O_NONBLOCK)
            print("✅ FFmpeg collegato! Trasmissione in corso...")
            # Segnala al generator_worker che può iniziare a produrre audio
            fifo_connected_event.set()
            audio_queue.put({"type": "metadata", "state": get_current_state()})
            fade_in_chunks_remaining = 0
            next_write_time = time.time()
            while True:
                if manual_block_override_index is None:
                    current_schedule_key = get_wallclock_schedule_key()
                    if current_schedule_key != last_schedule_key:
                        print(f"⏰ Cambio fascia palinsesto: {last_schedule_key} -> {current_schedule_key}. Tronco audio corrente.")
                        schedule_interrupt_event.set()
                        playout.stop_current_process("⏰ Termino il processo audio corrente per cambio fascia.")
                        playout.clear_queue()
                        last_schedule_key = current_schedule_key
                        write_state_files({"status": "OFFLINE"})

                if os.path.exists(CONTROL_FILE):
                    try:
                        with open(CONTROL_FILE, "r") as f:
                            cmd = f.read().strip()
                        os.remove(CONTROL_FILE)
                        
                        if cmd == "FORCE_NEXT":
                            schedule_interrupt_event.set()
                            schedule_data = scheduler.get_current_schedule()
                            times = sorted(schedule_data.keys())
                            manual_block_override_index = (current_active_index + 1) % len(times)
                            playout.stop_current_process("⏭️ Termino il processo audio corrente per skip.")
                            playout.clear_queue()
                            write_state_files({"status": "OFFLINE"})
                        elif cmd.startswith("FORCE_INDEX_"):
                            try:
                                target_idx = int(cmd.split("_")[2])
                                schedule_interrupt_event.set()
                                manual_block_override_index = target_idx
                                playout.stop_current_process("⏭️ Termino il processo audio corrente per cambio manuale.")
                                playout.clear_queue()
                                write_state_files({"status": "OFFLINE"})
                            except Exception as e:
                                print(f"⚠️ Errore FORCE_INDEX: {e}")
                        elif cmd == "REGEN_SCHEDULE":
                            schedule_interrupt_event.set()
                            manual_block_override_index = None
                            last_schedule_key = get_wallclock_schedule_key()
                            from schedule_generator import generate_schedule
                            generate_schedule()
                            write_state_files({"status": "OFFLINE"})
                        elif cmd.startswith("HOURLY_CHIME_READY"):
                            parts = cmd.split("|")
                            chime_file = parts[1] if len(parts) > 1 else CHIME_AUDIO_FILE
                            force_chime = len(parts) > 2 and parts[2] == "force"
                            
                            if not force_chime:
                                try:
                                    now = datetime.datetime.now()
                                    nearest_hour = (now + datetime.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
                                    current_hour_str = nearest_hour.strftime("%H:00")
                                    from schedule_generator import get_current_schedule
                                    schedule_data = get_current_schedule()
                                    if current_hour_str in schedule_data:
                                        continue
                                except Exception as e:
                                    print(f"⚠️ Errore controllo chime: {e}")

                            if os.path.exists(chime_file):
                                apply_preventive_fade_out_and_write(fifo_fd)
                                chime_info = {
                                    "status": "ON_AIR",
                                    "current_block": "chime",
                                    "current_title": "SEGNALE ORARIO",
                                    "next_block": "",
                                    "next_start": "",
                                    "breaking_news_available": False,
                                    "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
                                }
                                prev_state = get_current_state()
                                write_state_files(chime_info)

                                cmd_ffmpeg = [
                                    FFMPEG_CMD,
                                    "-hide_banner",
                                    "-loglevel", "error",
                                    "-i", chime_file,
                                    "-f", "s16le",
                                    "-ar", str(PCM_SAMPLE_RATE),
                                    "-ac", str(PCM_CHANNELS),
                                    "pipe:1"
                                ]
                                try:
                                    proc = subprocess.Popen(cmd_ffmpeg, stdout=subprocess.PIPE)
                                    while True:
                                        chunk_data = proc.stdout.read(PCM_CHUNK_BYTES)
                                        if not chunk_data:
                                            break
                                        write_fifo_chunk(fifo_fd, chunk_data)
                                    proc.wait()
                                except Exception as e:
                                    print(f"⚠️ Errore chime: {e}")
                                restore_after_interrupt(prev_state, "chime")
                                fade_in_chunks_remaining = 20
                        elif cmd == "TRIGGER_BREAKING_NEWS":
                            threading.Thread(target=lambda: subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "breaking_news_agent.py")])).start()
                        elif cmd == "TRIGGER_SPECIAL_BROADCAST_TEST":
                            def run_forced_breaking_news():
                                env = os.environ.copy()
                                env["FORCE_SEVERITY"] = "95"
                                subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "breaking_news_agent.py")], env=env)
                            threading.Thread(target=run_forced_breaking_news).start()
                        elif cmd.startswith("BREAKING_NEWS_READY"):
                            parts = cmd.split("|")
                            bn_file = parts[1] if len(parts) > 1 else ""
                            severity_score = int(parts[2]) if len(parts) > 2 else 0
                            reason = parts[3] if len(parts) > 3 else "Valutazione ordinaria"
                            
                            if os.path.exists(bn_file):
                                if severity_score >= 90:
                                    print(f"🚨 [Director] Innesco Edizione Straordinaria (Score {severity_score}): {reason}")
                                    apply_preventive_fade_out_and_write(fifo_fd)
                                    schedule_interrupt_event.set()
                                    playout.stop_current_process("🚨 Interruzione per Edizione Straordinaria.")
                                    playout.clear_queue()
                                    director_agent.notify_interrupt(reason, severity_score)
                                    fade_in_chunks_remaining = 20
                                else:
                                    apply_preventive_fade_out_and_write(fifo_fd)
                                    bn_info = {
                                        "status": "ON_AIR",
                                        "current_block": "breaking_news",
                                        "current_title": "ULTIM'ORA",
                                        "next_block": "Ripresa Palinsesto",
                                        "next_start": "",
                                        "breaking_news_available": False,
                                        "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
                                    }
                                    prev_state = get_current_state()
                                    write_state_files(bn_info)
                                    cmd_ffmpeg = [
                                        FFMPEG_CMD,
                                        "-hide_banner",
                                        "-loglevel", "error",
                                        "-i", bn_file,
                                        "-f", "s16le",
                                        "-ar", str(PCM_SAMPLE_RATE),
                                        "-ac", str(PCM_CHANNELS),
                                        "pipe:1"
                                    ]
                                    try:
                                        proc = subprocess.Popen(cmd_ffmpeg, stdout=subprocess.PIPE)
                                        while True:
                                            chunk_data = proc.stdout.read(PCM_CHUNK_BYTES)
                                            if not chunk_data:
                                                break
                                            write_fifo_chunk(fifo_fd, chunk_data)
                                        proc.wait()
                                    except Exception as e:
                                        print(f"⚠️ Errore breaking news: {e}")
                                    restore_after_interrupt(prev_state, "breaking news")
                                    fade_in_chunks_remaining = 20
                        elif cmd == "REVOKE_SPECIAL_BROADCAST" or cmd == "END_SPECIAL_BROADCAST":
                            print("🚨 [Director] Ricevuto comando di fine Edizione Straordinaria. Ripristino palinsesto.")
                            schedule_interrupt_event.set()
                            playout.stop_current_process("🚨 Fine Edizione Straordinaria.")
                            playout.clear_queue()
                            director_agent.handle_restore_after_interrupt()
                            fade_in_chunks_remaining = 20
                    except Exception as e:
                        print(f"⚠️ Errore comandi: {e}")

                try:
                    item = audio_queue.get_nowait()
                    if isinstance(item, dict) and item.get("type") == "metadata":
                        # Aggiorna solo i campi "display" — quelli che la Dashboard legge
                        # per mostrare titolo, blocco attivo, prossimo programma, ecc.
                        # I campi della macchina a stati (status, current_segment,
                        # scheduled_slot, interrupted_*) sono gestiti ESCLUSIVAMENTE
                        # dal DirectorAgent e non devono mai essere sovrascritti da
                        # block_info, che ha "status": "ON_AIR" hardcoded e non include
                        # current_segment — causando reset del loop E perdita del
                        # SPECIAL_BROADCAST durante l'edizione straordinaria.
                        _DISPLAY_FIELDS = {
                            "current_block", "current_title", "next_block",
                            "next_start", "breaking_news_available", "last_update",
                        }
                        existing_state = get_current_state()
                        for _field in _DISPLAY_FIELDS:
                            if _field in item["state"]:
                                existing_state[_field] = item["state"][_field]
                        write_state_files(existing_state)
                        audio_queue.task_done()
                        continue
                        
                    data = item["data"] if isinstance(item, dict) else item
                    if fade_in_chunks_remaining > 0:
                        import numpy as np
                        try:
                            samples = np.frombuffer(data, dtype=np.int16).copy()
                            idx = 20 - fade_in_chunks_remaining
                            start_factor = idx / 20
                            end_factor = (idx + 1) / 20
                            factors = np.linspace(start_factor, end_factor, len(samples))
                            data = (samples * factors).astype(np.int16).tobytes()
                            fade_in_chunks_remaining -= 1
                        except Exception as e:
                            print(f"⚠️ Errore fade-in: {e}")
                            
                    write_fifo_chunk(fifo_fd, data)
                    audio_queue.task_done()
                    
                    chunk_duration = len(data) / (2 * PCM_SAMPLE_RATE)
                    next_write_time += chunk_duration
                    sleep_time = next_write_time - time.time()
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    elif sleep_time < -0.5:
                        next_write_time = time.time()
                except queue.Empty:
                    if breaking_news_active:
                        breaking_news_active = False
                        schedule_interrupt_event.set()
                        playout.stop_current_process("🚨 Sblocco dopo Breaking News.")
                        playout.clear_queue()
                        write_state_files({"status": "OFFLINE"})
                        
                    try:
                        if not write_fifo_chunk(fifo_fd, silence, blocking=False):
                            time.sleep(0.02)
                        else:
                            chunk_duration = len(silence) / (2 * PCM_SAMPLE_RATE)
                            next_write_time += chunk_duration
                            sleep_time = next_write_time - time.time()
                            if sleep_time > 0:
                                time.sleep(sleep_time)
                            elif sleep_time < -0.5:
                                next_write_time = time.time()
                    except BrokenPipeError:
                        break
                except BrokenPipeError:
                    break
        except Exception as e:
            print(f"⚠️ Errore pipe: {e}")
            time.sleep(2)
        finally:
            # Se la FIFO si chiude (FFmpeg si disconnette), resettiamo l'evento
            # così il generator_worker si fermerà e aspetterà la riconnessione
            fifo_connected_event.clear()
            if fifo_fd is not None:
                try:
                    os.close(fifo_fd)
                except OSError:
                    pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Regia interrotta.")
        sys.exit(0)
