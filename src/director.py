import os
import sys
from dotenv import load_dotenv

# Carica le variabili dal file .env prima di qualsiasi altro modulo
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_base_dir, ".env"))

import subprocess
import time
import threading
import queue
import datetime
import signal
from newsica.audio.playout import AudioPlayout
from newsica.audio.settings import PCM_CHANNELS, PCM_CHUNK_BYTES, PCM_SAMPLE_RATE, resolve_ffmpeg_cmd
from newsica.broadcast import scheduler
from newsica.broadcast.scheduler import get_wallclock_schedule_key
from newsica.broadcast.runtime_state import ensure_folders, get_current_state, write_state_files
from newsica.broadcast.director_agent import DirectorAgent
from newsica.audio.fifo import FifoWriter, is_music_safe_for_chime
from newsica.broadcast.process_monitor import SubprocessSupervisor
from newsica.broadcast.control_bus import poll_control_file
from newsica.domain.playout_events import PlayoutEvent, PlayoutExecutionContext

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
shutdown_requested = threading.Event()
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
_singleton_lock = None
SHUTDOWN_GRACE_SECONDS = 3.0


def install_signal_handlers():
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)


def _handle_shutdown_signal(signum, frame):
    signal_name = signal.Signals(signum).name
    request_shutdown(f"📴 Arresto intenzionale del director ricevuto via {signal_name}.")


def _force_exit_after_grace_period(grace_seconds):
    time.sleep(grace_seconds)
    if shutdown_requested.is_set():
        print(f"⏹️ Shutdown del director ancora pendente dopo {grace_seconds:.1f}s, termino il processo.")
        os._exit(0)


def request_shutdown(reason, *, force_exit=True):
    if shutdown_requested.is_set():
        return
    print(reason)
    shutdown_requested.set()
    schedule_interrupt_event.set()
    fifo_connected_event.set()
    playout.stop_current_process("🛑 Arresto audio corrente per shutdown del director.")
    playout.clear_queue()
    if force_exit:
        threading.Thread(
            target=_force_exit_after_grace_period,
            args=(SHUTDOWN_GRACE_SECONDS,),
            daemon=True,
        ).start()


def wait_for_fifo_connection(poll_interval=0.5):
    while not shutdown_requested.is_set():
        if fifo_connected_event.wait(timeout=poll_interval):
            return not shutdown_requested.is_set()
    return False


def build_ordinary_breaking_state(prev_state, now_ts):
    return {
        "status": "ON_AIR",
        "current_block": "breaking_news",
        "current_title": "ULTIM'ORA",
        "current_segment": prev_state.get("current_segment", ""),
        "next_block": "Ripresa Palinsesto",
        "next_start": "",
        "scheduled_slot": prev_state.get("scheduled_slot", ""),
        "theme": prev_state.get("theme"),
        "breaking_news_available": False,
        "last_update": now_ts,
    }


def build_restart_recovery_state(existing_state, wallclock_slot, now_ts):
    state = dict(existing_state or {})
    status = state.get("status", "OFFLINE")

    if status == "SPECIAL_BROADCAST":
        recovered = dict(state)
        if recovered.get("current_segment") in {"intro", "broadcast_body"}:
            recovered["current_segment"] = "broadcast_waiting"
        recovered["last_update"] = now_ts
        return recovered

    if status != "ON_AIR":
        return {"status": "OFFLINE", "last_update": now_ts}

    scheduled_slot = state.get("scheduled_slot")
    current_block = state.get("current_block")
    if not scheduled_slot or scheduled_slot != wallclock_slot:
        return {"status": "OFFLINE", "last_update": now_ts}

    # Dopo un restart non possiamo riprendere un file PCM a metà voce.
    # I blocchi music_only vengono re-inizializzati (OFFLINE) perché il Director
    # per questo tipo di blocco non produce mai audio da _progress_current_block()
    # (restituisce TriggerNextBlockEvent() in loop → silenzio).
    # Con OFFLINE, _initialize_scheduled_block() viene chiamato e il PlayoutPlanner
    # mette subito in coda un PlayMusicDeadlineEvent → audio immediato al restart.
    recovered = dict(state)
    if current_block == "music_only":
        recovered["status"] = "OFFLINE"
        recovered["last_update"] = now_ts
        return recovered

    current_segment = recovered.get("current_segment", "") or ""
    is_music_segment = (
        current_segment == "music_rotation_until_deadline"
        or current_segment.startswith("music_")
    )
    if not is_music_segment:
        recovered["current_segment"] = "music_rotation_until_deadline"
        if current_block == "podcast":
            recovered["podcast_played"] = True
    recovered["last_update"] = now_ts
    return recovered


def handle_ordinary_breaking_news(
    fifo_writer,
    bn_file,
    *,
    now_ts,
    state_reader=get_current_state,
    state_writer=write_state_files,
    restore_fn=None,
    popen_factory=subprocess.Popen,
):
    global breaking_news_active
    if restore_fn is None:
        restore_fn = restore_after_interrupt

    fifo_writer.apply_preventive_fade_out_and_write()
    prev_state = state_reader()
    breaking_news_active = True
    bn_info = build_ordinary_breaking_state(prev_state, now_ts)
    state_writer(bn_info)
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
        proc = popen_factory(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        while True:
            chunk_data = proc.stdout.read(PCM_CHUNK_BYTES)
            if not chunk_data:
                break
            fifo_writer.write_chunk(chunk_data)
        proc.wait()
    except Exception as e:
        print(f"⚠️ Errore breaking news: {e}")
    finally:
        breaking_news_active = False
    restore_fn(prev_state, "breaking news")


def trigger_next_block():
    global manual_block_override_index
    manual_block_override_index = None
    schedule_interrupt_event.set()
    playout.stop_current_process("⏰ Termino il blocco corrente per cambio fascia.")
    playout.clear_queue()


def merge_display_state(existing_state, incoming_state):
    existing = dict(existing_state or {})
    incoming = dict(incoming_state or {})
    if existing.get("status") == "OFFLINE":
        return existing

    display_fields = {
        "current_block", "current_title", "next_block",
        "next_start", "breaking_news_available", "last_update",
        "current_music_title", "requested_by", "requested_title",
    }
    for field in display_fields:
        if field in incoming:
            existing[field] = incoming[field]
    return existing


def make_execution_context():
    def state_updater(**kwargs):
        state = get_current_state()
        if state.get("status") != "OFFLINE":
            state.update(kwargs)
            write_state_files(state)

    return PlayoutExecutionContext(
        playout=playout,
        state_reader=get_current_state,
        state_updater=state_updater,
        trigger_next_block=trigger_next_block,
    )


def execute_playout_event(event):
    global current_active_index
    if not isinstance(event, PlayoutEvent):
        raise TypeError(f"Unexpected director event type: {type(event)!r}")
    if event.active_idx is not None:
        current_active_index = event.active_idx
    event.execute(make_execution_context())


def generator_worker():
    global breaking_news_active, manual_block_override_index
    print("🤖 Thread Generatore (DirectorAgent Event Loop) avviato.")
    event_queue = []
    
    # Aspetta che la FIFO sia aperta da FFmpeg prima di pre-caricare audio.
    print("⏸️  Generator in attesa che FFmpeg apra la pipe audio...")
    if not wait_for_fifo_connection():
        print("🛑 Generator arrestato prima della connessione FIFO.")
        return
    print("▶️  Generator sbloccato — avvio ciclo palinsesto.")
    
    while not shutdown_requested.is_set():
        try:
            while breaking_news_active and not shutdown_requested.is_set():
                time.sleep(1)

            if shutdown_requested.is_set():
                break
                
            schedule_interrupt_event.clear()
            
            if event_queue:
                event = event_queue.pop(0)
            else:
                event = director_agent.decide_next_action(manual_block_override_index)
                if isinstance(event, list):
                    event_queue.extend(event)
                    continue
            
            if event is None:
                time.sleep(1)
                continue
            
            execute_playout_event(event)
                
        except Exception as e:
            if shutdown_requested.is_set():
                break
            print(f"💥 Errore nel ciclo del generatore DirectorAgent: {e}")
            time.sleep(5)



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
    install_signal_handlers()
    if not check_singleton("director"):
        sys.exit(1)
    
    print("🎬 Regia NewsicaTV avviata.")
    now_ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    recovered_state = build_restart_recovery_state(
        get_current_state(),
        get_wallclock_schedule_key(),
        now_ts,
    )
    if recovered_state.get("status") == "ON_AIR":
        print(
            "♻️ Recovery director: preservo lo slot corrente "
            f"{recovered_state.get('scheduled_slot')} in segmento "
            f"{recovered_state.get('current_segment')}."
        )
    elif recovered_state.get("status") == "SPECIAL_BROADCAST":
        print("♻️ Recovery director: ripristino stato di edizione straordinaria.")
    else:
        print("ℹ️ Recovery director: nessuno slot recuperabile, imposto OFFLINE.")
    write_state_files(recovered_state)
    
    threading.Thread(target=generator_worker, daemon=True).start()
    supervisor = SubprocessSupervisor(PYTHON_EXEC, BASE_DIR)
    supervisor.start_all()
    
    silence = b'\x00' * PCM_CHUNK_BYTES
    last_schedule_key = recovered_state.get("scheduled_slot") or get_wallclock_schedule_key()
    
    while not shutdown_requested.is_set():
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
            fifo_writer = FifoWriter(fifo_fd, audio_queue)
            while not shutdown_requested.is_set():
                if manual_block_override_index is None:
                    current_schedule_key = get_wallclock_schedule_key()
                    if current_schedule_key != last_schedule_key:
                        print(f"⏰ Cambio fascia palinsesto: {last_schedule_key} -> {current_schedule_key}. Tronco audio corrente.")
                        schedule_interrupt_event.set()
                        playout.stop_current_process("⏰ Termino il processo audio corrente per cambio fascia.")
                        playout.clear_queue()
                        last_schedule_key = current_schedule_key

                # Control Bus processing
                cmd_event = poll_control_file(CONTROL_FILE)
                if cmd_event:
                    try:
                        if cmd_event.name == "FORCE_NEXT":
                            schedule_interrupt_event.set()
                            schedule_data = scheduler.get_current_schedule()
                            times = sorted(schedule_data.keys())
                            manual_block_override_index = (current_active_index + 1) % len(times)
                            playout.stop_current_process("⏭️ Termino il processo audio corrente per skip.")
                            playout.clear_queue()
                        elif cmd_event.name == "FORCE_INDEX":
                            try:
                                target_idx = cmd_event.kwargs["target_idx"]
                                schedule_interrupt_event.set()
                                manual_block_override_index = target_idx
                                playout.stop_current_process("⏭️ Termino il processo audio corrente per cambio manuale.")
                                playout.clear_queue()
                            except Exception as e:
                                print(f"⚠️ Errore FORCE_INDEX: {e}")
                        elif cmd_event.name == "REGEN_SCHEDULE":
                            schedule_interrupt_event.set()
                            manual_block_override_index = None
                            last_schedule_key = get_wallclock_schedule_key()
                            from schedule_generator import generate_schedule
                            generate_schedule()
                            write_state_files({"status": "OFFLINE"})
                        elif cmd_event.name == "HOURLY_CHIME_READY":
                            chime_file = cmd_event.kwargs["chime_file"] or CHIME_AUDIO_FILE
                            if os.path.exists(chime_file):
                                current_state = get_current_state()
                                if not is_music_safe_for_chime(current_state):
                                    block = current_state.get("current_block", "unknown")
                                    segment = current_state.get("current_segment", "unknown")
                                    print(f"🔕 Segnale orario saltato: non interrompo speaker o contenuto parlato ({block}/{segment}).")
                                    continue
                                try:
                                    fifo_writer.overlay_chime_on_music(chime_file, silence)
                                except Exception as e:
                                    print(f"⚠️ Errore chime: {e}")
                            else:
                                print(f"⚠️ File segnale orario non trovato: {chime_file}")
                        elif cmd_event.name == "TRIGGER_BREAKING_NEWS":
                            threading.Thread(target=lambda: subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "breaking_news_agent.py")])).start()
                        elif cmd_event.name == "TRIGGER_SPECIAL_BROADCAST_TEST":
                            def run_forced_breaking_news():
                                env = os.environ.copy()
                                env["FORCE_SEVERITY"] = "95"
                                subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "breaking_news_agent.py")], env=env)
                            threading.Thread(target=run_forced_breaking_news).start()
                        elif cmd_event.name == "PLAY_PODCAST_IMMEDIATE":
                            podcast_file = cmd_event.kwargs["podcast_file"] or os.path.join(TMP_DIR, "audio.wav")
                            podcast_title = cmd_event.kwargs["podcast_title"]

                            if os.path.exists(podcast_file):
                                print(f"🎙️ [Director] Podcast immediato richiesto: {podcast_title}")
                                fifo_writer.apply_preventive_fade_out_and_write()
                                prev_state = get_current_state()
                                podcast_info = {
                                    "status": "ON_AIR",
                                    "current_block": "podcast",
                                    "current_title": podcast_title,
                                    "current_segment": "podcast_immediate",
                                    "next_block": prev_state.get("next_block", ""),
                                    "next_start": prev_state.get("next_start", ""),
                                    "scheduled_slot": prev_state.get("scheduled_slot"),
                                    "breaking_news_available": False,
                                    "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
                                }
                                write_state_files(podcast_info)

                                cmd_ffmpeg = [
                                    FFMPEG_CMD,
                                    "-hide_banner",
                                    "-loglevel", "error",
                                    "-i", podcast_file,
                                    "-f", "s16le",
                                    "-ar", str(PCM_SAMPLE_RATE),
                                    "-ac", str(PCM_CHANNELS),
                                    "pipe:1"
                                ]
                                try:
                                    proc = subprocess.Popen(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                                    while True:
                                        chunk_data = proc.stdout.read(PCM_CHUNK_BYTES)
                                        if not chunk_data:
                                            break
                                        fifo_writer.write_chunk(chunk_data)
                                    proc.wait()
                                except Exception as e:
                                    print(f"⚠️ Errore podcast immediato: {e}")
                                restore_after_interrupt(prev_state, "podcast immediato")
                                fade_in_chunks_remaining = 20
                            else:
                                print(f"⚠️ Podcast immediato non trovato: {podcast_file}")
                        elif cmd_event.name == "BREAKING_NEWS_READY":
                            bn_file = cmd_event.kwargs["bn_file"]
                            severity_score = cmd_event.kwargs["severity_score"]
                            reason = cmd_event.kwargs["reason"]
                            
                            if os.path.exists(bn_file):
                                if severity_score >= 90:
                                    print(f"🚨 [Director] Innesco Edizione Straordinaria (Score {severity_score}): {reason}")
                                    fifo_writer.apply_preventive_fade_out_and_write()
                                    schedule_interrupt_event.set()
                                    playout.stop_current_process("🚨 Interruzione per Edizione Straordinaria.")
                                    playout.clear_queue()
                                    special_event = director_agent.notify_interrupt(reason, severity_score)
                                    if special_event is not None:
                                        execute_playout_event(special_event)
                                    fade_in_chunks_remaining = 20
                                else:
                                    handle_ordinary_breaking_news(
                                        fifo_writer,
                                        bn_file,
                                        now_ts=time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    )
                                    fade_in_chunks_remaining = 20
                        elif cmd_event.name == "REVOKE_SPECIAL_BROADCAST":
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
                        # Aggiorna solo i campi display e non consolidare OFFLINE
                        # transitori come fonte di verita' runtime.
                        existing_state = get_current_state()
                        merged_state = merge_display_state(existing_state, item["state"])
                        if merged_state.get("status") != "OFFLINE":
                            write_state_files(merged_state)
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
                            
                    fifo_writer.write_chunk(data)
                    audio_queue.task_done()
                    
                    chunk_duration = len(data) / (2 * PCM_SAMPLE_RATE)
                    next_write_time += chunk_duration
                    sleep_time = next_write_time - time.time()
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    elif sleep_time < -0.5:
                        next_write_time = time.time()
                except queue.Empty:
                    if shutdown_requested.is_set():
                        break
                    if breaking_news_active:
                        breaking_news_active = False
                        schedule_interrupt_event.set()
                        playout.stop_current_process("🚨 Sblocco dopo Breaking News.")
                        playout.clear_queue()
                        write_state_files({"status": "OFFLINE"})
                        
                    try:
                        if not fifo_writer.write_chunk(silence, blocking=False):
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
            if shutdown_requested.is_set():
                break
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
    print("👋 Director arrestato in modo pulito.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        request_shutdown("📴 Interruzione da tastiera ricevuta.")
        print("\n👋 Regia interrotta.")
        sys.exit(0)
