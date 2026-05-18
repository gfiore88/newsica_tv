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

def get_random_music():
    files = glob.glob(os.path.join(MUSIC_DIR, "*.wav")) + glob.glob(os.path.join(MUSIC_DIR, "*.mp3"))
    if not files:
        return None
    return random.choice(files)

def get_filler_process(music_file):
    cmd = [
        "ffmpeg",
        "-i", music_file,
        "-f", "s16le",
        "-ar", "24000",
        "-ac", "1",
        "pipe:1"
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

def run_pipeline():
    print("\n--- 🔄 Avvio ciclo di aggiornamento news ---")
    
    # 1. Scraper
    print("Scraping news...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "src", "scraper.py")])
    
    # 2. LLM Processor
    print("Elaborazione testo (LLM)...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "src", "llm_processor.py")])
    
    # 3. TTS Generator
    print("Sintesi vocale (TTS)...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "src", "tts_generator.py")])

def mix_and_queue(music_file, voice_file):
    print(f"Mixaggio in corso: Voce + {os.path.basename(music_file)}")
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", voice_file,
        "-i", music_file,
        "-filter_complex", "[0:a]apad[voice_padded]; [1:a]volume=0.6[m]; [m][voice_padded]sidechaincompress=threshold=0.03:ratio=20:attack=50:release=1000[music]; [0:a][music]amix=inputs=2:duration=longest:dropout_transition=0",
        "-f", "s16le",
        "-ar", "24000",
        "-ac", "1",
        "pipe:1"
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    
    print("Caricamento audio nella coda...")
    count = 0
    while True:
        data = process.stdout.read(4096)
        if not data:
            break
        audio_queue.put(data) # Questo si blocca se la coda è piena
        count += 1
            
    process.wait()
    print(f"✅ Blocco audio caricato nella coda ({count} chunks).")

def generator_worker():
    print("🤖 Thread Generatore avviato.")
    # Genera il primo blocco
    run_pipeline()
    
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
                with open(voice_file, 'rb') as f:
                    while True:
                        data = f.read(4096)
                        if not data:
                            break
                        audio_queue.put(data)
            else:
                mix_and_queue(music_file, voice_file)
                
            print("🚀 Genero già il prossimo blocco in background...")
            
            # Rigenera le news per il prossimo blocco senza aspettare!
            run_pipeline()
            
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
    
    RATE = 48000
    CHUNK = 4096
    SLEEP_TIME = CHUNK / RATE
    silence = b'\x00' * CHUNK
    
    filler_proc = None
    
    while True:
        print("\n📡 In attesa che FFmpeg si colleghi alla pipe in lettura...")
        try:
            with open(AUDIO_PIPE, 'wb') as fifo:
                print("✅ FFmpeg collegato! Trasmissione in corso...")
                while True:
                    try:
                        # Prende i dati dalla coda con un timeout breve
                        data = audio_queue.get(timeout=0.1)
                        
                        # Se c'è un filler attivo, lo chiudiamo perché abbiamo di nuovo le news!
                        if filler_proc is not None:
                            print("📰 News pronte! Fermo la musica di riempimento.")
                            filler_proc.terminate()
                            filler_proc.wait()
                            filler_proc = None
                            
                        fifo.write(data)
                        fifo.flush()
                        audio_queue.task_done()
                    except queue.Empty:
                        # Se la coda è vuota (es. durante la generazione), usa il filler
                        if filler_proc is None:
                            music_file = get_random_music()
                            if music_file:
                                print(f"🎵 Coda vuota! Avvio musica di riempimento: {os.path.basename(music_file)}")
                                filler_proc = get_filler_process(music_file)
                        
                        if filler_proc:
                            data = filler_proc.stdout.read(CHUNK)
                            if not data:
                                # Il file è finito
                                filler_proc.wait()
                                filler_proc = None
                                continue
                            
                            try:
                                fifo.write(data)
                                fifo.flush()
                                time.sleep(SLEEP_TIME)
                            except BrokenPipeError:
                                print("❌ Pipe rotta (FFmpeg si è disconnesso).")
                                break
                        else:
                            # Se non c'è musica, manda silenzio
                            try:
                                fifo.write(silence)
                                fifo.flush()
                                time.sleep(SLEEP_TIME)
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
            if filler_proc is not None:
                print("🛑 Chiudo il processo di riempimento...")
                filler_proc.terminate()
                filler_proc.wait()
                filler_proc = None

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Regia interrotta dall'utente.")
        sys.exit(0)
