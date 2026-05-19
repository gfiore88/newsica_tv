import os
import time
import subprocess
import random
import glob
import sys
import threading
import queue
import json
import datetime
from schedule_generator import get_current_schedule, generate_schedule

# Cartelle di progetto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
MUSIC_DIR = os.path.join(BASE_DIR, "assets", "music")
JINGLES_DIR = os.path.join(BASE_DIR, "assets", "jingles")
CLASSIC_JINGLE_FILE = os.path.join(JINGLES_DIR, "newsicatv_jingle.mp3")
SPORT_JINGLE_FILE = os.path.join(JINGLES_DIR, "jingle_sport.mp3")
AUDIO_PIPE = os.path.join(TMP_DIR, "audio_pipe")
STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
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

PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python3")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = sys.executable
PCM_SAMPLE_RATE = 24000
PCM_CHANNELS = 1
PCM_CHUNK_BYTES = 4096
FFMPEG_CMD = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
if not os.path.exists(FFMPEG_CMD):
    FFMPEG_CMD = "/opt/homebrew/bin/ffmpeg"
if not os.path.exists(FFMPEG_CMD):
    FFMPEG_CMD = "ffmpeg"

# Coda per l'audio (5000 chunks = circa 7 minuti di audio)
audio_queue = queue.Queue(maxsize=5000)

manual_block_override_index = None
current_active_index = 0
last_music_file = None

def ensure_folders():
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump({"status": "OFFLINE"}, f)

    # Pre-popola i file letti dall'overlay FFmpeg se non esistono.
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

    if not os.path.exists(AUDIO_PIPE):
        try:
            os.mkfifo(AUDIO_PIPE)
            print(f"✅ Pipe creata in {AUDIO_PIPE}")
        except OSError as e:
            print(f"⚠️ Errore creazione pipe: {e}")

_MUSIC_CACHE = []

def get_random_music(exclude=None):
    global _MUSIC_CACHE
    if not _MUSIC_CACHE:
        _MUSIC_CACHE = glob.glob(os.path.join(MUSIC_DIR, "*.wav")) + glob.glob(os.path.join(MUSIC_DIR, "*.mp3"))
    if not _MUSIC_CACHE:
        return None
    candidates = [path for path in _MUSIC_CACHE if path != exclude]
    if not candidates:
        candidates = _MUSIC_CACHE
    return random.choice(candidates)

queue_lock = threading.RLock()
breaking_news_active = False
current_generator_process = None
schedule_interrupt_event = threading.Event()

def clear_audio_queue():
    cleared = 0
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
            audio_queue.task_done()
            cleared += 1
        except queue.Empty:
            break
    return cleared

def stop_current_process(reason=""):
    global current_generator_process
    process = current_generator_process
    if not process:
        return

    if reason:
        print(reason)
    try:
        process.terminate()
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=1)
        except Exception as e:
            print(f"⚠️ Errore kill processo audio corrente: {e}")
    except Exception as e:
        print(f"⚠️ Errore terminazione processo audio corrente: {e}")
    finally:
        current_generator_process = None

def queue_item(item):
    while True:
        if schedule_interrupt_event.is_set() or breaking_news_active:
            return False
        try:
            audio_queue.put(item, timeout=0.5)
            return True
        except queue.Full:
            continue

def queue_pcm_from_file(audio_file, block_info=None, is_breaking_news=False):
    global current_generator_process
    if block_info:
        audio_queue.put({"type": "metadata", "state": block_info})
    cmd = [
        FFMPEG_CMD,
        "-hide_banner",
        "-loglevel", "error",
        "-i", audio_file,
        "-f", "s16le",
        "-ar", str(PCM_SAMPLE_RATE),
        "-ac", str(PCM_CHANNELS),
        "pipe:1"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    if not is_breaking_news:
        current_generator_process = process
        
    count = 0
    while True:
        if not is_breaking_news and (breaking_news_active or schedule_interrupt_event.is_set()):
            print("⏭️ Interrompo il caricamento audio regolare.")
            process.terminate()
            break
            
        data = process.stdout.read(PCM_CHUNK_BYTES)
        if not data:
            break
        if not is_breaking_news:
            if not queue_item({"type": "audio", "data": data}):
                process.terminate()
                break
        else:
            audio_queue.put({"type": "audio", "data": data})
        count += 1
        
    process.wait()
    if not is_breaking_news:
        current_generator_process = None
    print(f"✅ Audio voce caricato nella coda ({count} chunks).")

def queue_jingle(jingle_file, label="jingle"):
    global current_generator_process
    if not os.path.exists(jingle_file):
        print(f"⚠️ Jingle non trovato: {jingle_file}")
        return True

    print(f"🎶 Lancio {label}: {os.path.basename(jingle_file)}")
    cmd = [
        FFMPEG_CMD,
        "-hide_banner",
        "-loglevel", "error",
        "-i", jingle_file,
        "-f", "s16le",
        "-ar", str(PCM_SAMPLE_RATE),
        "-ac", str(PCM_CHANNELS),
        "pipe:1"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    current_generator_process = process

    while True:
        if breaking_news_active or schedule_interrupt_event.is_set():
            print(f"⏭️ Interrompo {label}.")
            process.terminate()
            break

        data = process.stdout.read(PCM_CHUNK_BYTES)
        if not data:
            break
        if not queue_item({"type": "audio", "data": data}):
            process.terminate()
            break

    process.wait()
    current_generator_process = None
    return not schedule_interrupt_event.is_set() and not breaking_news_active

def get_jingle_for_block(block_type):
    jingles = {
        "sport": (SPORT_JINGLE_FILE, "jingle sport"),
    }
    return jingles.get(block_type, (CLASSIC_JINGLE_FILE, "jingle NewsicaTV"))

def add_rubric_intro_to_script(title, character):
    script_file = os.path.join(TMP_DIR, "script.txt")
    if not os.path.exists(script_file):
        return

    intros = {
        "news": f"È il momento di {title}, la rubrica di informazione di NewsicaTV.",
        "sport": f"Ora spazio a {title}, la rubrica sportiva di NewsicaTV.",
        "meteo": f"Apriamo {title}, il nostro aggiornamento meteo su NewsicaTV.",
        "wellness": f"Comincia {title}, la rubrica benessere di NewsicaTV.",
    }
    intro = intros.get(character, f"Comincia {title}, una rubrica di NewsicaTV.")
    with open(script_file, "r", encoding="utf-8") as f:
        script = f.read().strip()
    if script.startswith(intro):
        return
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(f"{intro}\n\n{script}")

def run_pipeline(character="news", title=None):
    print(f"\n--- 🔄 Avvio ciclo di aggiornamento news ({character}) ---")
    
    # 1. Scraper
    print("Scraping news...")
    subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "scraper.py")], check=True)
    
    # 2. LLM Processor
    print("Elaborazione testo (LLM)...")
    subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "llm_processor.py"), character], check=True)

    if title:
        add_rubric_intro_to_script(title, character)
    
    # 3. TTS Generator
    print("Sintesi vocale (TTS)...")
    subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "tts_generator.py"), character], check=True)

def mix_and_queue(music_file, voice_file, block_info=None):
    global current_generator_process
    print(f"Mixaggio in corso: Voce + {os.path.basename(music_file)}")
    
    if block_info:
        audio_queue.put({"type": "metadata", "state": block_info})
        
    cmd = [
        FFMPEG_CMD,
        "-y",
        "-i", voice_file,
        "-i", music_file,
        "-filter_complex", "[0:a]volume=1.5,asplit=2[v_main][v_side]; [1:a]volume=0.25[m]; [m][v_side]sidechaincompress=threshold=0.03:ratio=20:attack=50:release=1000[music]; [v_main][music]amix=inputs=2:duration=first:dropout_transition=0",
        "-f", "s16le",
        "-ar", str(PCM_SAMPLE_RATE),
        "-ac", str(PCM_CHANNELS),
        "pipe:1"
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    current_generator_process = process
    
    print("Caricamento audio nella coda...")
    count = 0
    while True:
        if breaking_news_active or schedule_interrupt_event.is_set():
            print("⏭️ Interrompo il mixaggio regolare.")
            process.terminate()
            break
            
        data = process.stdout.read(PCM_CHUNK_BYTES)
        if not data:
            break
        if not queue_item({"type": "audio", "data": data}):
            process.terminate()
            break
        count += 1
            
    process.wait()
    current_generator_process = None
    print(f"✅ Blocco audio caricato nella coda ({count} chunks).")

def queue_music_track(deadline):
    global current_generator_process, last_music_file
    if datetime.datetime.now() >= deadline or schedule_interrupt_event.is_set() or breaking_news_active:
        return

    music_file = get_random_music(exclude=last_music_file)
    if not music_file:
        time.sleep(1)
        return
    last_music_file = music_file

    print(f"🎵 Brano musicale di riempimento: {os.path.basename(music_file)}")
    cmd = [
        FFMPEG_CMD,
        "-hide_banner",
        "-loglevel", "error",
        "-i", music_file,
        "-vn",
        "-filter:a", "volume=0.8",
        "-f", "s16le",
        "-ar", str(PCM_SAMPLE_RATE),
        "-ac", str(PCM_CHANNELS),
        "pipe:1"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    current_generator_process = process

    while datetime.datetime.now() < deadline:
        if breaking_news_active or schedule_interrupt_event.is_set():
            process.terminate()
            break

        data = process.stdout.read(PCM_CHUNK_BYTES)
        if not data:
            break
        if not queue_item({"type": "audio", "data": data}):
            process.terminate()
            break

    if process.poll() is None:
        process.terminate()
    process.wait()
    current_generator_process = None

def schedule_deadline(next_time_key):
    now = datetime.datetime.now()
    hour, minute = [int(part) for part in next_time_key.split(":")]
    deadline = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if deadline <= now:
        deadline += datetime.timedelta(days=1)
    return deadline

def get_current_block_info():
    global manual_block_override_index, current_active_index
    schedule_data = get_current_schedule()
    times = sorted(schedule_data.keys())
    
    if manual_block_override_index is None:
        now = datetime.datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        current_time_key = times[0]
        for t in times:
            if t <= current_time_str:
                current_time_key = t
            else:
                break
        current_active_index = times.index(current_time_key)
    else:
        current_active_index = manual_block_override_index
        
    current_time_key = times[current_active_index]
    block = schedule_data[current_time_key]
    
    next_index = (current_active_index + 1) % len(times)
    next_time_key = times[next_index]
    next_block = schedule_data[next_time_key]
    
    return block["type"], block["title"], next_block["title"], next_time_key, current_time_key

def get_wallclock_schedule_key():
    schedule_data = get_current_schedule()
    times = sorted(schedule_data.keys())
    current_time_str = datetime.datetime.now().strftime("%H:%M")
    current_time_key = times[0]
    for t in times:
        if t <= current_time_str:
            current_time_key = t
        else:
            break
    return current_time_key

def build_block_info(block_type, title, next_title, next_time):
    return {
        "status": "ON_AIR",
        "current_block": block_type,
        "current_title": title,
        "next_block": next_title,
        "next_start": next_time,
        "breaking_news_available": False,
        "last_update": ""
    }

def write_accent_files(block_type):
    active_key = block_type if block_type in ACCENT_FILES else "news"
    for key, accent_file in ACCENT_FILES.items():
        with open(accent_file, "w") as f:
            f.write(" " if key == active_key else "")

def enqueue_current_schedule_metadata():
    current_type, current_title, next_title, next_time, _ = get_current_block_info()
    audio_queue.put({"type": "metadata", "state": build_block_info(current_type, current_title, next_title, next_time)})
    return True

def generator_worker():
    global breaking_news_active
    print("🤖 Thread Generatore avviato.")
    
    while True:
        try:
            # Se c'è una breaking news attiva, aspetta che finisca prima di avviare un nuovo ciclo
            while breaking_news_active:
                print("⏳ Generatore in attesa: Breaking News in corso...")
                time.sleep(1)
                
            schedule_interrupt_event.clear()
            current_type, current_title, next_title, next_time, current_time = get_current_block_info()
            
            print(f"🚀 Genero blocco in background: {current_title} ({current_type})")
            if current_type != "music_only":
                run_pipeline(current_type, current_title)
            
            # Ricontrolla se si è attivata una breaking news durante la generazione
            while breaking_news_active:
                print("⏳ Generatore in attesa: Breaking News in corso...")
                time.sleep(1)

            if schedule_interrupt_event.is_set():
                print("⏭️ Fascia cambiata durante la generazione: scarto il blocco appena preparato.")
                continue
                
            voice_file = os.path.join(TMP_DIR, "audio.wav")
            music_file = get_random_music()
            
            block_info = build_block_info(current_type, current_title, next_title, next_time)
            
            if current_type == "music_only":
                if not queue_item({"type": "metadata", "state": block_info}):
                    continue
                queue_music_track(schedule_deadline(next_time))
                continue

            if not os.path.exists(voice_file):
                print("❌ Errore: file voce non generato. Riprovo tra 10 secondi...")
                time.sleep(10)
                continue

            if not queue_item({"type": "metadata", "state": block_info}):
                continue
            jingle_file, jingle_label = get_jingle_for_block(current_type)
            if not queue_jingle(jingle_file, jingle_label):
                continue
                
            if not music_file:
                print("⚠️ Nessuna musica trovata. Uso solo la voce.")
                queue_pcm_from_file(voice_file)
            else:
                mix_and_queue(music_file, voice_file)

            if not schedule_interrupt_event.is_set() and not breaking_news_active:
                queue_music_track(schedule_deadline(next_time))
                
        except Exception as e:
            print(f"💥 Errore nel ciclo del generatore: {e}")
            time.sleep(10)


def check_singleton(name):
    import fcntl
    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")
    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        global _singleton_lock
        _singleton_lock = f
        f.write(str(os.getpid()))
        f.flush()
        return True
    except (IOError, OSError):
        print(f"❌ ERRORE: Un'altra istanza di {name} è già in esecuzione!")
        return False


def main():
    global manual_block_override_index, current_active_index, breaking_news_active
    ensure_folders()
    if not check_singleton("director"):
        print("❌ Uscita immediata per prevenire conflitti.")
        sys.exit(1)
    
    print("🎬 Regia NewsicaTV avviata.")
    print("💡 Assicurati che lo streaming FFmpeg stia leggendo da 'tmp/audio_pipe'")
    
    # Avvia il thread che genera le news in background
    t = threading.Thread(target=generator_worker, daemon=True)
    t.start()
    
    # Avvia ticker agent in background
    ticker_thread = threading.Thread(target=lambda: subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "ticker_agent.py")]), daemon=True)
    ticker_thread.start()
    
    silence = b'\x00' * PCM_CHUNK_BYTES
    last_schedule_key = get_wallclock_schedule_key()
    
    while True:
        print("\n📡 In attesa che FFmpeg si colleghi alla pipe in lettura...")
        try:
            with open(AUDIO_PIPE, 'wb') as fifo:
                print("✅ FFmpeg collegato! Trasmissione in corso...")
                enqueue_current_schedule_metadata()
                while True:
                    if manual_block_override_index is None:
                        current_schedule_key = get_wallclock_schedule_key()
                        if current_schedule_key != last_schedule_key:
                            print(f"⏰ Cambio fascia palinsesto: {last_schedule_key} -> {current_schedule_key}. Tronco audio corrente.")
                            schedule_interrupt_event.set()
                            stop_current_process("⏰ Termino il processo audio corrente per cambio fascia.")
                            cleared = clear_audio_queue()
                            print(f"⏰ Coda audio svuotata ({cleared} elementi).")
                            last_schedule_key = current_schedule_key

                    if os.path.exists(CONTROL_FILE):
                        try:
                            with open(CONTROL_FILE, "r") as f:
                                cmd = f.read().strip()
                            os.remove(CONTROL_FILE)
                            
                            if cmd == "FORCE_NEXT":
                                print("⏭️ Comando ricevuto: FORCE_NEXT. Svuoto la coda audio!")
                                schedule_interrupt_event.set()
                                schedule_data = get_current_schedule()
                                times = sorted(schedule_data.keys())
                                manual_block_override_index = (current_active_index + 1) % len(times)
                                print(f"⏭️ Salto al blocco successivo con indice manuale: {manual_block_override_index}")

                                stop_current_process("⏭️ Termino il processo audio corrente per skip.")
                                clear_audio_queue()
                            elif cmd.startswith("FORCE_INDEX_"):
                                try:
                                    target_idx = int(cmd.split("_")[2])
                                    print(f"⏭️ Comando ricevuto: FORCE_INDEX_{target_idx}. Imposto indice manuale!")
                                    schedule_interrupt_event.set()
                                    manual_block_override_index = target_idx
                                    
                                    stop_current_process("⏭️ Termino il processo audio corrente per cambio manuale.")
                                    clear_audio_queue()
                                except Exception as e:
                                    print(f"⚠️ Errore nell'elaborazione di FORCE_INDEX: {e}")
                            elif cmd == "REGEN_SCHEDULE":
                                print("📅 Comando ricevuto: REGEN_SCHEDULE.")
                                schedule_interrupt_event.set()
                                manual_block_override_index = None
                                last_schedule_key = get_wallclock_schedule_key()
                                generate_schedule()
                            elif cmd == "TRIGGER_BREAKING_NEWS":
                                print("🚨 Comando ricevuto: TRIGGER_BREAKING_NEWS. Avvio agente in background...")
                                threading.Thread(target=lambda: subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "breaking_news_agent.py")])).start()
                            elif cmd.startswith("BREAKING_NEWS_READY"):
                                parts = cmd.split("|")
                                bn_file = parts[1] if len(parts) > 1 else ""
                                print("🚨 Comando ricevuto: BREAKING_NEWS_READY. Svuoto la coda per ultim'ora!")

                                # Impostiamo subito il flag
                                breaking_news_active = True
                                
                                # Terminiamo il processo regolare corrente per sbloccare la coda
                                stop_current_process("🚨 Termino il processo di generazione regolare corrente per far spazio alla Breaking News.")
                                
                                clear_audio_queue()
                                        
                                if os.path.exists(bn_file):
                                    bn_info = {
                                        "status": "ON_AIR",
                                        "current_block": "breaking_news",
                                        "current_title": "🚨 ULTIM'ORA",
                                        "next_block": "Ripresa Palinsesto",
                                        "next_start": "",
                                        "breaking_news_available": False,
                                        "last_update": ""
                                    }
                                    # Carichiamo come Breaking News in modo che non venga abortito da se stesso
                                    queue_pcm_from_file(bn_file, bn_info, is_breaking_news=True)
                        except Exception as e:
                            print(f"⚠️ Errore comandi: {e}")
 
                    try:
                        item = audio_queue.get_nowait()
                        
                        if isinstance(item, dict) and item.get("type") == "metadata":
                            item["state"]["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                            try:
                                with open(STATE_FILE, "w") as sf:
                                    json.dump(item["state"], sf, indent=2)

                                # Scrive i testi letti dall'overlay di FFmpeg.
                                with open(PROGRAM_FILE, "w") as pf:
                                    pf.write(item["state"]["current_title"].upper())
                                next_title = item["state"].get("next_block", "--")
                                next_start = item["state"].get("next_start")
                                next_label = f"A seguire: {next_title}"
                                if next_start:
                                    next_label = f"{next_label} - {next_start}"
                                with open(NEXT_PROGRAM_FILE, "w") as nf:
                                    nf.write(next_label)
                                write_accent_files(item["state"].get("current_block", "news"))
                            except Exception as e:
                                print(f"⚠️ Errore scrittura stato: {e}")
                            audio_queue.task_done()
                            continue
                            
                        data = item["data"] if isinstance(item, dict) else item
                        fifo.write(data)
                        fifo.flush()
                        audio_queue.task_done()
                    except queue.Empty:
                        if breaking_news_active:
                            print("🚨 Coda vuota: Breaking News completata. Ripristino palinsesto regolare.")
                            breaking_news_active = False
                            schedule_interrupt_event.set()
                            stop_current_process("🚨 Sblocco eventuale processo audio rimasto dopo la Breaking News.")
                            clear_audio_queue()
                            enqueue_current_schedule_metadata()
                            
                        # Mantiene sempre viva la FIFO: se la generazione e' in corso,
                        # FFmpeg riceve silenzio PCM invece di restare senza input.
                        try:
                            fifo.write(silence)
                            fifo.flush()
                        except BrokenPipeError:
                            print("❌ Pipe rotta (FFmpeg si è disconnesso).")
                            break
                    except BrokenPipeError:
                        print("❌ Pipe rotta (FFmpeg si è disconnesso).")
                        break
        except Exception as e:
            print(f"⚠️ Errore nell'apertura della pipe: {e}")
            time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Regia interrotta dall'utente.")
        sys.exit(0)
