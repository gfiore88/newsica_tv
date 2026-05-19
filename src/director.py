import os
import time
import subprocess
import random
import glob
import sys
import threading
import queue

# Cartelle di progetto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
MUSIC_DIR = os.path.join(BASE_DIR, "assets", "music")
AUDIO_PIPE = os.path.join(TMP_DIR, "audio_pipe")
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

def queue_pcm_from_file(audio_file):
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
        audio_queue.put(data)
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

def mix_and_queue(music_file, voice_file):
    print(f"Mixaggio in corso: Voce + {os.path.basename(music_file)}")
    
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
        audio_queue.put(data) # Questo si blocca se la coda è piena
        count += 1
            
    process.wait()
    print(f"✅ Blocco audio caricato nella coda ({count} chunks).")

CHARACTERS = ["wellness", "news", "sport", "meteo"]
char_idx = 0

def generator_worker():
    global char_idx
    print("🤖 Thread Generatore avviato.")
    # Genera il primo blocco
    run_pipeline(CHARACTERS[char_idx])
    char_idx = (char_idx + 1) % len(CHARACTERS)
    
    while True:
        try:
            voice_file = os.path.join(TMP_DIR, "audio.wav")
            music_file = get_random_music()
            
            if not os.path.exists(voice_file):
                print("❌ Errore: file voce non generato. Riprovo tra 10 secondi...")
                time.sleep(10)
                continue
                
            if not music_file:
                print("⚠️ Nessuna musica trovata. Uso solo la voce.")
                queue_pcm_from_file(voice_file)
            else:
                mix_and_queue(music_file, voice_file)
                
            print("🚀 Genero già il prossimo blocco in background...")
            
            # Rigenera le news per il prossimo blocco senza aspettare!
            run_pipeline(CHARACTERS[char_idx])
            char_idx = (char_idx + 1) % len(CHARACTERS)
            
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
    
    silence = b'\x00' * PCM_CHUNK_BYTES
    
    while True:
        print("\n📡 In attesa che FFmpeg si colleghi alla pipe in lettura...")
        try:
            with open(AUDIO_PIPE, 'wb') as fifo:
                print("✅ FFmpeg collegato! Trasmissione in corso...")
                while True:
                    try:
                        data = audio_queue.get_nowait()
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
