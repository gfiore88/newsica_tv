import os
import sys
import time
import subprocess
import json
import requests
import re
from kokoro_onnx import Kokoro
import soundfile as sf

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
FFMPEG_CMD = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg") else "ffmpeg"

def generate_breaking_news():
    print("🚨 Avvio pipeline Breaking News...")
    
    # 1. Recupero la prima notizia di ultimora da raw_news.json
    raw_news_path = os.path.join(TMP_DIR, "raw_news.json")
    notizia = None
    if os.path.exists(raw_news_path):
        try:
            with open(raw_news_path, "r", encoding="utf-8") as f:
                news_items = json.load(f)
                # Cerca ansa_ultimora
                for item in news_items:
                    if "ansa_ultimora" in item.get("source", ""):
                        notizia = item
                        break
        except Exception as e:
            print(f"⚠️ Errore nel caricamento delle news: {e}")
            
    # Testo di fallback drammatico
    testo_default = (
        "Interrompiamo le trasmissioni per un'Edizione Straordinaria. "
        "Un evento di eccezionale importanza è stato appena battuto dalle agenzie di stampa nazionale. "
        "Tutti i dettagli e le ripercussioni sul nostro portale. Restate sintonizzati su Newsica TV per tutti gli aggiornamenti in tempo reale."
    )
    
    testo = testo_default
    
    if notizia:
        titolo = notizia.get("title", "")
        sintesi = notizia.get("summary", "")
        news_text = f"TITOLO: {titolo}\nSINTESI: {sintesi}"
        print(f"📰 Notizia di ultim'ora selezionata: {titolo}")
        
        # 2. Rielaborazione testo tramite LLM (Ollama locale)
        OLLAMA_URL = "http://localhost:11434/api/generate"
        MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:12b")
        SYSTEM_PROMPT = (
            "Sei la conduttrice di NewsicaTV.\n"
            "Il tuo compito è prendere una singola notizia importante e trasformarla in un comunicato urgente, drammatico ed emozionante per un'Edizione Straordinaria televisiva improvvisa.\n"
            "Linee guida:\n"
            "1. Inizia SEMPRE esattamente con: \"Interrompiamo le trasmissioni per un'Edizione Straordinaria.\"\n"
            "2. Scrivi con un tono calmo ma estremamente urgente, drammatico ed autorevole.\n"
            "3. Spiega la notizia in modo chiaro e conciso. Massimo 3 frasi totali.\n"
            "4. Concludi con: \"Restate sintonizzati su NewsicaTV per ulteriori aggiornamenti.\"\n"
            "5. NON usare parentesi, note di regia o elenchi. Produci ESCLUSIVAMENTE il testo del copione da leggere."
        )
        
        payload = {
            "model": MODEL_NAME,
            "system": SYSTEM_PROMPT,
            "prompt": news_text,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.4,
                "num_predict": 300
            }
        }
        
        try:
            print("🤖 Elaborazione testo con Ollama...")
            response = requests.post(OLLAMA_URL, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()
            testo_generato = result.get("response", "").strip()
            if testo_generato:
                testo = testo_generato
                print(f"✅ Testo Breaking News generato: {testo}")
        except Exception as e:
            print(f"⚠️ Errore con Ollama, uso testo semplificato: {e}")
            testo = f"Interrompiamo le trasmissioni per un'Edizione Straordinaria. Ultim'ora dell'Ansa: {titolo}. Restate sintonizzati su NewsicaTV per ulteriori aggiornamenti."
    
    # 3. Pulizia testo per TTS
    testo = re.sub(r"\*+", "", testo)
    testo = re.sub(r"\s+", " ", testo)
    testo = testo.replace("...", ". ")
    
    # 4. Sintesi Vocale del Copione
    print("🎙️ Sintesi vocale tramite Kokoro AI...")
    voice_audio = os.path.join(TMP_DIR, "voice_breaking.wav")
    try:
        # Carichiamo i file ONNX e bin dalla cartella principale del progetto
        onnx_path = os.path.join(BASE_DIR, "kokoro-v1.0.onnx")
        voices_path = os.path.join(BASE_DIR, "voices-v1.0.bin")
        kokoro = Kokoro(onnx_path, voices_path)
        samples, sample_rate = kokoro.create(testo, voice="if_sara", speed=1.1, lang="it")
        sf.write(voice_audio, samples, sample_rate)
        print("✅ Voce Breaking News generata con successo.")
    except Exception as e:
        print(f"❌ Errore durante Kokoro TTS: {e}")
        # Fallback a None
        voice_audio = None
        
    # 5. Generazione dell'allarme sonoro (triplo impulso elettronico)
    print("🔔 Generazione jingle allarme...")
    alarm_audio = os.path.join(TMP_DIR, "alarm_jingle.wav")
    subprocess.run([
        FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=850:duration=0.5",
        "-f", "lavfi", "-i", "sine=frequency=0:duration=0.2",
        "-f", "lavfi", "-i", "sine=frequency=850:duration=0.5",
        "-f", "lavfi", "-i", "sine=frequency=0:duration=0.2",
        "-f", "lavfi", "-i", "sine=frequency=850:duration=0.8",
        "-filter_complex", "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1",
        "-ar", "24000", "-ac", "1", alarm_audio
    ])
    
    # 6. Concatenazione di Allarme + Voce
    bn_audio = os.path.join(TMP_DIR, "breaking_news.wav")
    if voice_audio and os.path.exists(voice_audio):
        print("🎛️ Unione allarme + copione vocale...")
        subprocess.run([
            FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "error",
            "-i", alarm_audio,
            "-i", voice_audio,
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1",
            "-ar", "24000", "-ac", "1", bn_audio
        ])
    else:
        # Se Kokoro fallisce, usiamo solo l'allarme
        print("⚠️ Solo allarme utilizzato a causa di errore TTS.")
        subprocess.run([
            FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "error",
            "-i", alarm_audio,
            "-ar", "24000", "-ac", "1", bn_audio
        ])
        
    # 7. Invio comando di ready al regista
    cmd = f"BREAKING_NEWS_READY|{bn_audio}"
    with open(CONTROL_FILE, "w") as f:
        f.write(cmd)
        
    print("✅ Breaking News completa. Segnale pronto inviato al regista.")

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
