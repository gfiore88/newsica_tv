import os
import time
import subprocess
import random
import glob
import sys

# ... (resto delle definizioni invariato) ...

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

def mix_and_pipe(music_file, voice_file, fifo):
    print(f"Mixaggio in corso: Voce + {os.path.basename(music_file)}")
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", voice_file,
        "-i", music_file,
        "-filter_complex", "[1:a]volume=0.1[music]; [0:a][music]amix=inputs=2:duration=first",
        "-f", "s16le",
        "-ar", "24000",
        "-ac", "1",
        "pipe:1"
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    print("Inviando l'audio alla pipe...")
    while True:
        data = process.stdout.read(4096)
        if not data:
            break
        fifo.write(data)
        fifo.flush() # Forza la scrittura
            
    process.wait()
    print("✅ Blocco audio inviato alla pipe.")

def main():
    ensure_folders()
    
    print("🎬 Regia NewsicaTV avviata.")
    print("💡 Assicurati che lo streaming FFmpeg stia leggendo da 'tmp/audio_pipe'")
    
    # Apriamo la pipe in scrittura UNA VOLTA SOLA e la teniamo aperta per sempre
    # Questo impedisce a FFmpeg di ricevere EOF e chiudersi!
    print("In attesa che FFmpeg si colleghi alla pipe in lettura...")
    with open(AUDIO_PIPE, 'wb') as fifo:
        while True:
            try:
                # Esegui la pipeline per generare i file
                run_pipeline()
                
                voice_file = os.path.join(TMP_DIR, "audio.wav")
                music_file = get_random_music()
                
                if not os.path.exists(voice_file):
                    print("❌ Errore: file voce non generato. Riprovo tra 10 secondi...")
                    time.sleep(10)
                    continue
                    
                if not music_file:
                    print("⚠️ Nessuna musica trovata in assets/music/. Uso solo la voce.")
                    with open(voice_file, 'rb') as f:
                        fifo.write(f.read())
                        fifo.flush()
                else:
                    mix_and_pipe(music_file, voice_file, fifo)
                    
                print("⏳ Attesa 5 minuti prima del prossimo aggiornamento...")
                time.sleep(300) # Attendi 5 minuti prima di aggiornare le news
                
            except KeyboardInterrupt:
                print("\n👋 Regia interrotta dall'utente.")
                break
            except Exception as e:
                print(f"💥 Errore nel ciclo di regia: {e}")
                time.sleep(10)

if __name__ == "__main__":
    main()
