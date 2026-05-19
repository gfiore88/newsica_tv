import os
import sys
import time
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
FFMPEG_CMD = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg") else "ffmpeg"

def generate_breaking_news():
    print("🚨 Avvio pipeline Breaking News...")
    
    # Simuliamo il tempo di uno scraper o di una chiamata LLM (es. 5 secondi)
    time.sleep(5)
    
    # 1. Recupero Testo (Mock)
    testo = "Interrompiamo le trasmissioni per un'ultima ora. Un evento eccezionale è appena stato battuto dalle agenzie. Restate sintonizzati su Newsica TV per tutti i dettagli in arrivo."
    
    # 2. Sintesi Audio
    bn_audio = os.path.join(TMP_DIR, "breaking_news.wav")
    
    # Per questo MVP generiamo un tono di emergenza o usiamo il tts se disponibile.
    # Usiamo FFmpeg per creare un effetto "allarme" + voce simulata
    print("Generazione audio di emergenza...")
    subprocess.run([
        FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=800:duration=1.5",
        "-f", "lavfi", "-i", "sine=frequency=600:duration=3.5",
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1",
        "-ar", "24000", "-ac", "1", bn_audio
    ])
    
    # 3. Invio comando di ready al regista
    cmd = f"BREAKING_NEWS_READY|{bn_audio}"
    with open(CONTROL_FILE, "w") as f:
        f.write(cmd)
        
    print("✅ Breaking News generata. Comando inoltrato a director.py.")

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

if __name__ == "__main__":
    if not check_singleton("breaking_news_agent"):
        print("❌ Uscita immediata per prevenire conflitti.")
        sys.exit(1)
    generate_breaking_news()
