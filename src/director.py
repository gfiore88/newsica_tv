import os
import time
import subprocess
import sys
import threading
import queue
import json
import datetime
from schedule_generator import get_current_schedule, generate_schedule
from newsica.audio.jingles import get_jingle_for_block
from newsica.audio.playout import AudioPlayout
from newsica.audio.settings import PCM_CHANNELS, PCM_CHUNK_BYTES, PCM_SAMPLE_RATE, resolve_ffmpeg_cmd
from newsica.domain.characters import get_character

# Cartelle di progetto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
AUDIO_PIPE = os.path.join(TMP_DIR, "audio_pipe")
STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
PROGRAM_FILE = os.path.join(TMP_DIR, "current_program.txt")
NEXT_PROGRAM_FILE = os.path.join(TMP_DIR, "next_program.txt")
CHIME_AUDIO_FILE = os.path.join(TMP_DIR, "hourly_chime.wav")
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

# Coda per l'audio (5000 chunks = circa 7 minuti di audio)
audio_queue = queue.Queue(maxsize=5000)

manual_block_override_index = None
current_active_index = 0
breaking_news_active = False
schedule_interrupt_event = threading.Event()
playout = AudioPlayout(
    audio_queue,
    schedule_interrupt_event,
    lambda: breaking_news_active,
)
FFMPEG_CMD = resolve_ffmpeg_cmd()

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

def write_state_files(state):
    state = dict(state)
    state["last_update"] = state.get("last_update") or time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(STATE_FILE, "w") as sf:
        json.dump(state, sf, indent=2)
    with open(PROGRAM_FILE, "w") as pf:
        pf.write(state.get("current_title", "").upper())

    next_title = state.get("next_block", "")
    next_start = state.get("next_start")
    next_label = f"A seguire: {next_title}" if next_title else ""
    if next_label and next_start:
        next_label = f"{next_label} - {next_start}"
    with open(NEXT_PROGRAM_FILE, "w") as nf:
        nf.write(next_label)
    write_accent_files(state.get("current_block", "news"))

def get_current_schedule_state():
    current_type, current_title, next_title, next_time, _ = get_current_block_info()
    return build_block_info(current_type, current_title, next_title, next_time)

def restore_after_interrupt(prev_state, label):
    transient_blocks = {"chime", "breaking_news"}
    state = prev_state if prev_state and prev_state.get("current_block") not in transient_blocks else get_current_schedule_state()
    try:
        write_state_files(state)
    except Exception as e:
        print(f"⚠️ Errore ripristino stato dopo {label}: {e}")

def write_fifo_chunk(fifo_fd, data, blocking=True):
    view = memoryview(data)
    written_total = 0
    while written_total < len(view):
        try:
            next_end = min(written_total + 512, len(view))
            written = os.write(fifo_fd, view[written_total:next_end])
            if written == 0:
                raise BrokenPipeError
            written_total += written
        except BlockingIOError:
            if not blocking:
                return False
            time.sleep(0.02)
    return True

def enqueue_current_schedule_metadata():
    audio_queue.put({"type": "metadata", "state": get_current_schedule_state()})
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
                
            multipart_indicator = os.path.join(TMP_DIR, "is_multipart.txt")
            voice_file = os.path.join(TMP_DIR, "audio.wav")
            
            block_info = build_block_info(current_type, current_title, next_title, next_time)
            
            if current_type == "music_only":
                if not playout.queue_item({"type": "metadata", "state": block_info}):
                    continue
                playout.queue_music_track(schedule_deadline(next_time))
                continue

            # Controlliamo se è uno show radiofonico multi-part
            is_multipart = False
            num_parts = 0
            if os.path.exists(multipart_indicator):
                try:
                    with open(multipart_indicator, "r") as f:
                        num_parts = int(f.read().strip())
                    if num_parts > 0:
                        # Verifica che tutti i file audio part1..partN esistano
                        all_exist = True
                        for i in range(1, num_parts + 1):
                            if not os.path.exists(os.path.join(TMP_DIR, f"audio_part{i}.wav")):
                                all_exist = False
                                break
                        is_multipart = all_exist
                except Exception as e:
                    print(f"⚠️ Errore nel caricamento dei metadati multi-part: {e}")
                    is_multipart = False

            if not is_multipart and not os.path.exists(voice_file):
                print("❌ Errore: file voce non generato. Riprovo tra 10 secondi...")
                time.sleep(10)
                continue

            if not playout.queue_item({"type": "metadata", "state": block_info}):
                continue
            
            jingle_file, jingle_label = get_jingle_for_block(current_type)
            
            if is_multipart:
                print(f"📻 Avvio show radiofonico multi-part per {current_title} ({num_parts} parti)!")
                
                # 1. Jingle di apertura rubrica
                if not playout.queue_jingle(jingle_file, jingle_label):
                    continue
                
                # 2. Riproduzione sequenziale delle parti con intermezzi musicali di 3 brani completi
                last_used_music = None
                for i in range(1, num_parts + 1):
                    if schedule_interrupt_event.is_set() or breaking_news_active:
                        break
                        
                    part_file = os.path.join(TMP_DIR, f"audio_part{i}.wav")
                    print(f"🎤 Messa in onda Parte {i}/{num_parts}...")
                    
                    # Riproduce la voce mixata col sottofondo
                    music_file = playout.get_random_music(exclude=last_used_music)
                    if not music_file:
                        playout.queue_pcm_from_file(part_file)
                    else:
                        last_used_music = music_file
                        playout.mix_and_queue(music_file, part_file)
                        
                    # Se non è l'ultima parte, riproduce 3 brani musicali interi (stacco radiofonico)
                    if i < num_parts:
                        songs_between = 3 # Numero di canzoni intere tra un intervento e l'altro
                        print(f"🎵 Stacco musicale radiofonico: riproduzione di {songs_between} brani completi...")
                        for s in range(songs_between):
                            if schedule_interrupt_event.is_set() or breaking_news_active:
                                break
                            playout.queue_single_music_track()
            else:
                # Flusso classico a parte singola
                if not playout.queue_jingle(jingle_file, jingle_label):
                    continue
                
                music_file = playout.get_random_music()
                if not music_file:
                    print("⚠️ Nessuna musica trovata. Uso solo la voce.")
                    playout.queue_pcm_from_file(voice_file)
                else:
                    playout.mix_and_queue(music_file, voice_file)

            if not schedule_interrupt_event.is_set() and not breaking_news_active:
                playout.queue_music_track(schedule_deadline(next_time))
                
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

    # Avvia hourly chime agent in background
    chime_thread = threading.Thread(
        target=lambda: subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "hourly_chime_agent.py")]),
        daemon=True
    )
    chime_thread.start()
    
    silence = b'\x00' * PCM_CHUNK_BYTES
    last_schedule_key = get_wallclock_schedule_key()
    
    while True:
        print("\n📡 In attesa che FFmpeg si colleghi alla pipe in lettura...")
        fifo_fd = None
        try:
            fifo_fd = os.open(AUDIO_PIPE, os.O_WRONLY | os.O_NONBLOCK)
            print("✅ FFmpeg collegato! Trasmissione in corso...")
            enqueue_current_schedule_metadata()
            while True:
                    if manual_block_override_index is None:
                        current_schedule_key = get_wallclock_schedule_key()
                        if current_schedule_key != last_schedule_key:
                            print(f"⏰ Cambio fascia palinsesto: {last_schedule_key} -> {current_schedule_key}. Tronco audio corrente.")
                            schedule_interrupt_event.set()
                            playout.stop_current_process("⏰ Termino il processo audio corrente per cambio fascia.")
                            cleared = playout.clear_queue()
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

                                playout.stop_current_process("⏭️ Termino il processo audio corrente per skip.")
                                playout.clear_queue()
                            elif cmd.startswith("FORCE_INDEX_"):
                                try:
                                    target_idx = int(cmd.split("_")[2])
                                    print(f"⏭️ Comando ricevuto: FORCE_INDEX_{target_idx}. Imposto indice manuale!")
                                    schedule_interrupt_event.set()
                                    manual_block_override_index = target_idx

                                    playout.stop_current_process("⏭️ Termino il processo audio corrente per cambio manuale.")
                                    playout.clear_queue()
                                except Exception as e:
                                    print(f"⚠️ Errore nell'elaborazione di FORCE_INDEX: {e}")
                            elif cmd == "REGEN_SCHEDULE":
                                print("📅 Comando ricevuto: REGEN_SCHEDULE.")
                                schedule_interrupt_event.set()
                                manual_block_override_index = None
                                last_schedule_key = get_wallclock_schedule_key()
                                generate_schedule()
                            elif cmd.startswith("HOURLY_CHIME_READY"):
                                parts = cmd.split("|")
                                chime_file = parts[1] if len(parts) > 1 else CHIME_AUDIO_FILE
                                force_chime = len(parts) > 2 and parts[2] == "force"
                                print(f"🔔 Comando ricevuto: HOURLY_CHIME_READY. Riproduco rintocco orario!")

                                # Salta il rintocco se coincide con l'inizio di un blocco del palinsesto (es. 16:00)
                                if not force_chime:
                                    try:
                                        now = datetime.datetime.now()
                                        nearest_hour = (now + datetime.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
                                        current_hour_str = nearest_hour.strftime("%H:00")
                                        schedule_data = get_current_schedule()
                                        if current_hour_str in schedule_data:
                                            block_title = schedule_data[current_hour_str]["title"]
                                            print(f"🔔 Segnale orario delle {current_hour_str} annullato: coincide con l'inizio del blocco '{block_title}'.")
                                            continue
                                    except Exception as e:
                                        print(f"⚠️ Errore durante il controllo del palinsesto per chime: {e}")

                                if os.path.exists(chime_file):
                                    print("🔔 Riproduzione sincrona del rintocco orario in corso...")
                                    chime_info = {
                                        "status": "ON_AIR",
                                        "current_block": "chime",
                                        "current_title": "SEGNALE ORARIO",
                                        "next_block": "",
                                        "next_start": "",
                                        "breaking_news_available": False,
                                        "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
                                    }

                                    # Salviamo lo stato precedente per ripristinarlo
                                    prev_state = None
                                    if os.path.exists(STATE_FILE):
                                        try:
                                            with open(STATE_FILE, "r") as sf:
                                                prev_state = json.load(sf)
                                        except Exception:
                                            pass

                                    # Aggiorna la grafica per il segnale orario
                                    try:
                                        with open(STATE_FILE, "w") as sf:
                                            json.dump(chime_info, sf, indent=2)
                                        with open(PROGRAM_FILE, "w") as pf:
                                            pf.write("SEGNALE ORARIO")
                                        with open(NEXT_PROGRAM_FILE, "w") as nf:
                                            nf.write("")
                                        write_accent_files("chime")
                                    except Exception as e:
                                        print(f"⚠️ Errore aggiornamento stato per chime: {e}")

                                    # Riproduce il file direttamente sulla FIFO (pausa temporanea ma preserva la coda)
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
                                        chime_chunks = 0
                                        while True:
                                            chunk_data = proc.stdout.read(PCM_CHUNK_BYTES)
                                            if not chunk_data:
                                                break
                                            write_fifo_chunk(fifo_fd, chunk_data)
                                            chime_chunks += 1
                                        proc.wait()
                                        print(f"🔔 Rintocco orario riprodotto con successo ({chime_chunks} chunks).")
                                    except Exception as e:
                                        print(f"⚠️ Errore riproduzione chime: {e}")

                                    restore_after_interrupt(prev_state, "chime")
                                else:
                                    print(f"⚠️ File rintocco non trovato: {chime_file}")
                            elif cmd == "TRIGGER_BREAKING_NEWS":
                                print("🚨 Comando ricevuto: TRIGGER_BREAKING_NEWS. Avvio agente in background...")
                                threading.Thread(target=lambda: subprocess.run([PYTHON_EXEC, os.path.join(BASE_DIR, "src", "breaking_news_agent.py")])).start()
                            elif cmd.startswith("BREAKING_NEWS_READY"):
                                parts = cmd.split("|")
                                bn_file = parts[1] if len(parts) > 1 else ""
                                print("🚨 Comando ricevuto: BREAKING_NEWS_READY. Eseguo riproduzione sincrona!")

                                if os.path.exists(bn_file):
                                    bn_info = {
                                        "status": "ON_AIR",
                                        "current_block": "breaking_news",
                                        "current_title": "ULTIM'ORA",
                                        "next_block": "Ripresa Palinsesto",
                                        "next_start": "",
                                        "breaking_news_available": False,
                                        "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
                                    }

                                    # Salviamo lo stato precedente per ripristinarlo
                                    prev_state = None
                                    if os.path.exists(STATE_FILE):
                                        try:
                                            with open(STATE_FILE, "r") as sf:
                                                prev_state = json.load(sf)
                                        except Exception:
                                            pass

                                    # Aggiorna la grafica per l'Ultim'Ora
                                    try:
                                        with open(STATE_FILE, "w") as sf:
                                            json.dump(bn_info, sf, indent=2)
                                        with open(PROGRAM_FILE, "w") as pf:
                                            pf.write("ULTIM'ORA")
                                        with open(NEXT_PROGRAM_FILE, "w") as nf:
                                            nf.write("Ripresa Palinsesto")
                                        write_accent_files("breaking_news")
                                    except Exception as e:
                                        print(f"⚠️ Errore scrittura stato per breaking news: {e}")

                                    # Riproduce la breaking news direttamente sulla FIFO (pausa temporanea ma preserva la coda)
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
                                        bn_chunks = 0
                                        while True:
                                            chunk_data = proc.stdout.read(PCM_CHUNK_BYTES)
                                            if not chunk_data:
                                                break
                                            write_fifo_chunk(fifo_fd, chunk_data)
                                            bn_chunks += 1
                                        proc.wait()
                                        print(f"🚨 Breaking News riprodotta con successo ({bn_chunks} chunks).")
                                    except Exception as e:
                                        print(f"⚠️ Errore riproduzione breaking news: {e}")

                                    restore_after_interrupt(prev_state, "breaking news")
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
                        write_fifo_chunk(fifo_fd, data)
                        audio_queue.task_done()
                    except queue.Empty:
                        if breaking_news_active:
                            print("🚨 Coda vuota: Breaking News completata. Ripristino palinsesto regolare.")
                            breaking_news_active = False
                            schedule_interrupt_event.set()
                            playout.stop_current_process("🚨 Sblocco eventuale processo audio rimasto dopo la Breaking News.")
                            playout.clear_queue()
                            enqueue_current_schedule_metadata()
                            
                        # Mantiene sempre viva la FIFO: se la generazione e' in corso,
                        # FFmpeg riceve silenzio PCM invece di restare senza input.
                        try:
                            if not write_fifo_chunk(fifo_fd, silence, blocking=False):
                                time.sleep(0.02)
                        except BrokenPipeError:
                            print("❌ Pipe rotta (FFmpeg si è disconnesso).")
                            break
                    except BrokenPipeError:
                        print("❌ Pipe rotta (FFmpeg si è disconnesso).")
                        break
        except Exception as e:
            print(f"⚠️ Errore nell'apertura della pipe: {e}")
            time.sleep(2)
        finally:
            if fifo_fd is not None:
                try:
                    os.close(fifo_fd)
                except OSError:
                    pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Regia interrotta dall'utente.")
        sys.exit(0)
