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
AUDIO_PIPE = os.path.join(TMP_DIR, "audio_pipe")
STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
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

def ensure_folders():
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump({"status": "OFFLINE"}, f)
    if not os.path.exists(AUDIO_PIPE):
        try:
            os.mkfifo(AUDIO_PIPE)
            print(f"✅ Pipe creata in {AUDIO_PIPE}")
        except OSError as e:
            print(f"⚠️ Errore creazione pipe: {e}")

_MUSIC_CACHE = []

def get_random_music():
    global _MUSIC_CACHE
    if not _MUSIC_CACHE:
        _MUSIC_CACHE = glob.glob(os.path.join(MUSIC_DIR, "*.wav")) + glob.glob(os.path.join(MUSIC_DIR, "*.mp3"))
    if not _MUSIC_CACHE:
        return None
    return random.choice(_MUSIC_CACHE)

def queue_pcm_from_file(audio_file, block_info=None):
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
    count = 0
    while True:
        data = process.stdout.read(PCM_CHUNK_BYTES)
        if not data:
            break
        audio_queue.put({"type": "audio", "data": data})
        count += 1
    process.wait()
    print(f"✅ Audio voce caricato nella coda ({count} chunks).")

def run_pipeline(character="news"):
    print(f"\n--- 🔄 Avvio ciclo di aggiornamento news ({character}) ---")
    
    # 1. Scraper
    print("Scraping news...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "src", "scraper.py")], check=True)
    
    # 2. LLM Processor
    print("Elaborazione testo (LLM)...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "src", "llm_processor.py"), character], check=True)
    
    # 3. TTS Generator
    print("Sintesi vocale (TTS)...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "src", "tts_generator.py"), character], check=True)

def mix_and_queue(music_file, voice_file, block_info=None):
    print(f"Mixaggio in corso: Voce + {os.path.basename(music_file)}")
    
    if block_info:
        audio_queue.put({"type": "metadata", "state": block_info})
        
    cmd = [
        FFMPEG_CMD,
        "-y",
        "-i", voice_file,
        "-i", music_file,
        "-filter_complex", "[0:a]apad[voice_padded]; [1:a]volume=0.6[m]; [m][voice_padded]sidechaincompress=threshold=0.03:ratio=20:attack=50:release=1000[music]; [0:a][music]amix=inputs=2:duration=longest:dropout_transition=0",
        "-f", "s16le",
        "-ar", str(PCM_SAMPLE_RATE),
        "-ac", str(PCM_CHANNELS),
        "pipe:1"
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    
    print("Caricamento audio nella coda...")
    count = 0
    while True:
        data = process.stdout.read(PCM_CHUNK_BYTES)
        if not data:
            break
        audio_queue.put({"type": "audio", "data": data}) # Questo si blocca se la coda è piena
        count += 1
            
    process.wait()
    print(f"✅ Blocco audio caricato nella coda ({count} chunks).")

def get_current_block_info():
    schedule_data = get_current_schedule()
    now = datetime.datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    times = sorted(schedule_data.keys())
    current_time_key = times[0]
    for t in times:
        if t <= current_time_str:
            current_time_key = t
        else:
            break
            
    block = schedule_data[current_time_key]
    
    next_index = times.index(current_time_key) + 1
    next_time_key = times[next_index] if next_index < len(times) else times[0]
    next_block = schedule_data[next_time_key]
    
    return block["type"], block["title"], next_block["title"]

def generator_worker():
    print("🤖 Thread Generatore avviato.")
    
    while True:
        try:
            current_type, current_title, next_title = get_current_block_info()
            
            print(f"🚀 Genero blocco in background: {current_title} ({current_type})")
            run_pipeline(current_type)
            
            voice_file = os.path.join(TMP_DIR, "audio.wav")
            music_file = get_random_music()
            
            block_info = {
                "status": "ON_AIR",
                "current_block": current_type,
                "current_title": current_title,
                "next_block": next_title,
                "breaking_news_available": False,
                "last_update": "" # sara' popolato al momento della messa in onda
            }
            
            if not os.path.exists(voice_file):
                print("❌ Errore: file voce non generato. Riprovo tra 10 secondi...")
                time.sleep(10)
                continue
                
            if not music_file:
                print("⚠️ Nessuna musica trovata. Uso solo la voce.")
                queue_pcm_from_file(voice_file, block_info)
            else:
                mix_and_queue(music_file, voice_file, block_info)
                
        except Exception as e:
            print(f"💥 Errore nel ciclo del generatore: {e}")
            time.sleep(10)


def main():
    ensure_folders()
    
    print("🎬 Regia NewsicaTV avviata.")
    print("💡 Assicurati che lo streaming FFmpeg stia leggendo da 'tmp/audio_pipe'")
    
    # Avvia il thread che genera le news in background
    t = threading.Thread(target=generator_worker, daemon=True)
    t.start()
    
    # Avvia ticker agent in background
    ticker_thread = threading.Thread(target=lambda: subprocess.run([sys.executable, os.path.join(BASE_DIR, "src", "ticker_agent.py")]), daemon=True)
    ticker_thread.start()
    
    silence = b'\x00' * PCM_CHUNK_BYTES
    
    while True:
        print("\n📡 In attesa che FFmpeg si colleghi alla pipe in lettura...")
        try:
            with open(AUDIO_PIPE, 'wb') as fifo:
                print("✅ FFmpeg collegato! Trasmissione in corso...")
                while True:
                    if os.path.exists(CONTROL_FILE):
                        try:
                            with open(CONTROL_FILE, "r") as f:
                                cmd = f.read().strip()
                            os.remove(CONTROL_FILE)
                            
                            if cmd == "FORCE_NEXT":
                                print("⏭️ Comando ricevuto: FORCE_NEXT. Svuoto la coda audio!")
                                while not audio_queue.empty():
                                    try:
                                        audio_queue.get_nowait()
                                        audio_queue.task_done()
                                    except queue.Empty:
                                        break
                            elif cmd == "REGEN_SCHEDULE":
                                print("📅 Comando ricevuto: REGEN_SCHEDULE.")
                                generate_schedule()
                            elif cmd == "TRIGGER_BREAKING_NEWS":
                                print("🚨 Comando ricevuto: TRIGGER_BREAKING_NEWS. Avvio agente in background...")
                                import threading
                                threading.Thread(target=lambda: subprocess.run([sys.executable, os.path.join(BASE_DIR, "src", "breaking_news_agent.py")])).start()
                            elif cmd.startswith("BREAKING_NEWS_READY"):
                                parts = cmd.split("|")
                                bn_file = parts[1] if len(parts) > 1 else ""
                                print("🚨 Comando ricevuto: BREAKING_NEWS_READY. Svuoto la coda per ultim'ora!")
                                while not audio_queue.empty():
                                    try:
                                        audio_queue.get_nowait()
                                        audio_queue.task_done()
                                    except queue.Empty:
                                        break
                                        
                                if os.path.exists(bn_file):
                                    bn_info = {
                                        "status": "ON_AIR",
                                        "current_block": "breaking_news",
                                        "current_title": "🚨 ULTIM'ORA",
                                        "next_block": "Ripresa Palinsesto",
                                        "breaking_news_available": False,
                                        "last_update": ""
                                    }
                                    import threading
                                    threading.Thread(target=queue_pcm_from_file, args=(bn_file, bn_info)).start()
                        except Exception as e:
                            print(f"⚠️ Errore comandi: {e}")

                    try:
                        item = audio_queue.get_nowait()
                        
                        if isinstance(item, dict) and item.get("type") == "metadata":
                            item["state"]["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                            try:
                                with open(STATE_FILE, "w") as sf:
                                    json.dump(item["state"], sf, indent=2)
                            except Exception as e:
                                print(f"⚠️ Errore scrittura stato: {e}")
                            audio_queue.task_done()
                            continue
                            
                        data = item["data"] if isinstance(item, dict) else item
                        fifo.write(data)
                        fifo.flush()
                        audio_queue.task_done()
                    except queue.Empty:
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
