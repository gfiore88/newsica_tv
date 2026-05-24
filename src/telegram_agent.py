import json
import os
import subprocess
import sys
import time
from pathlib import Path
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Importiamo il nostro gestore code
sys.path.append(os.path.join(BASE_DIR, "src"))
from newsica.audio.settings import resolve_ffmpeg_cmd
from newsica.audio.telegram_voices import enqueue_voice

TMP_DIR = Path(BASE_DIR) / "tmp"
RUNTIME_DIR = Path(BASE_DIR) / "runtime"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FFMPEG_CMD = resolve_ffmpeg_cmd()

# Creiamo le cartelle necessarie
ORIGINAL_DIR = TMP_DIR / "telegram_voices" / "original"
CONVERTED_DIR = TMP_DIR / "telegram_voices" / "converted"
ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
CONVERTED_DIR.mkdir(parents=True, exist_ok=True)


def check_singleton(name):
    import fcntl
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")
    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.write(str(os.getpid()))
        f.flush()
        return f
    except (IOError, OSError):
        print(f"ERRORE: Un'altra istanza di {name} e' gia' in esecuzione.")
        return None


def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Errore nell'invio del messaggio di cortesia a Telegram: {e}")


def process_voice_message(token, message):
    chat_id = message["chat"]["id"]
    from_user = message.get("from", {})
    username = from_user.get("username")
    first_name = from_user.get("first_name", "Ascoltatore")
    
    voice = message.get("voice")
    if not voice:
        return
        
    file_id = voice["file_id"]
    duration = voice.get("duration", 0)
    
    # 1. Recupera informazioni sul file
    get_file_url = f"https://api.telegram.org/bot{token}/getFile"
    try:
        r = requests.get(get_file_url, params={"file_id": file_id}, timeout=10)
        if r.status_code != 200:
            print(f"❌ Errore getFile Telegram: HTTP {r.status_code} - {r.text}")
            send_message(token, chat_id, "Spiacenti, si è verificato un errore nel recupero del tuo vocale. Riprova tra poco!")
            return
        
        file_info = r.json().get("result", {})
        file_path = file_info.get("file_path")
        if not file_path:
            print("❌ Percorso file vuoto nella risposta getFile.")
            return
            
    except Exception as e:
        print(f"❌ Eccezione durante getFile: {e}")
        return

    # 2. Scarica il file audio (.ogg Opus)
    download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    original_file_path = ORIGINAL_DIR / f"{file_id}.ogg"
    try:
        print(f"📥 Scaricamento del vocale da {first_name} (@{username or 'no_user'}): {download_url}")
        r = requests.get(download_url, timeout=20)
        if r.status_code != 200:
            print(f"❌ Errore download file Telegram: HTTP {r.status_code}")
            return
        original_file_path.write_bytes(r.content)
    except Exception as e:
        print(f"❌ Eccezione durante download: {e}")
        return

    # 3. Converti il file audio in WAV PCM a 24000Hz (Mono, 16-bit)
    converted_file_path = CONVERTED_DIR / f"{file_id}.wav"
    try:
        print(f"🔄 Conversione FFmpeg in corso per {file_id}...")
        cmd = [
            FFMPEG_CMD,
            "-y",
            "-i", str(original_file_path),
            "-ar", "24000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(converted_file_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            print(f"❌ Errore conversione FFmpeg:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
            send_message(token, chat_id, "Spiacenti, si è verificato un errore nell'elaborazione del file audio. Riprova con un altro vocale!")
            return
        print(f"✅ Conversione completata: {converted_file_path}")
    except Exception as e:
        print(f"❌ Eccezione durante la conversione FFmpeg: {e}")
        return

    # 4. Accoda il messaggio (gestendo l'auto-approvazione)
    try:
        # Rileggiamo da .env ad ogni messaggio per supportare cambi a caldo se l'utente modifica l'env
        load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
        auto_approve = os.getenv("TELEGRAM_AUTO_APPROVE", "false").lower() in ("true", "1", "yes")
        initial_status = "approved" if auto_approve else "pending"
        
        enqueue_voice(
            author_username=username,
            author_first_name=first_name,
            file_id=file_id,
            duration=duration,
            original_path=str(original_file_path),
            converted_path=str(converted_file_path),
            status=initial_status,
        )
        
        if initial_status == "approved":
            print(f"🎙️ Vocale Telegram accodato con AUTO-APPROVAZIONE da {first_name} (@{username or 'no_username'})")
            send_message(
                token,
                chat_id,
                f"Grazie {first_name}! Il tuo vocale è stato ricevuto ed è già stato approvato per la messa in onda su NewsicaTV! Rimani all'ascolto! 📻"
            )
        else:
            print(f"🎙️ Vocale Telegram accodato con successo (in attesa approvazione) da {first_name} (@{username or 'no_username'})")
            send_message(
                token,
                chat_id,
                f"Grazie {first_name}! Il tuo vocale è stato ricevuto ed è in attesa di approvazione da parte della regia di NewsicaTV. Rimani all'ascolto! 📻"
            )
    except Exception as e:
        print(f"❌ Errore durante l'accodamento del vocale: {e}")


def run_telegram_loop(token):
    print("🚀 [TELEGRAM AGENT] Avvio loop di lettura aggiornamenti via Telegram API (Long Polling)...")
    offset = 0
    
    while True:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {
            "offset": offset,
            "timeout": 30,
            "allowed_updates": json.dumps(["message"])
        }
        
        try:
            r = requests.get(url, params=params, timeout=35)
            if r.status_code == 200:
                data = r.json()
                updates = data.get("result", [])
                
                for update in updates:
                    update_id = update["update_id"]
                    offset = update_id + 1
                    
                    message = update.get("message", {})
                    # Gestiamo solo i messaggi che contengono un file vocale
                    if "voice" in message:
                        try:
                            process_voice_message(token, message)
                        except Exception as pe:
                            print(f"❌ Errore durante process_voice_message: {pe}")
                    elif "text" in message:
                        # Risposta di benvenuto automatica se l'utente scrive testo o lancia /start
                        chat_id = message["chat"]["id"]
                        first_name = message.get("from", {}).get("first_name", "Ascoltatore")
                        send_message(
                            token,
                            chat_id,
                            f"Ciao {first_name}! Benvenuto su NewsicaTV! 📻\n\nInviami un messaggio vocale (un memo vocale) per farlo ascoltare in diretta durante la nostra trasmissione live H24 su YouTube!"
                        )
                        
            elif r.status_code == 401:
                print("❌ [TELEGRAM AGENT] Token del Bot non valido (Errore 401). Verifica il valore in .env.")
                time.sleep(30)
            else:
                print(f"⚠️ [TELEGRAM AGENT] Errore HTTP {r.status_code} da Telegram API. Riprovo in 10s...")
                time.sleep(10)
                
        except Exception as e:
            print(f"❌ [TELEGRAM AGENT] Eccezione nel loop: {e}. Riprovo in 10s...")
            time.sleep(10)


def main():
    global TELEGRAM_BOT_TOKEN
    lock = check_singleton("telegram_agent")
    if not lock:
        sys.exit(1)
        
    print("🎬 Telegram Agent avviato.")
    
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ [TELEGRAM AGENT] TELEGRAM_BOT_TOKEN non configurato in .env. L'agente rimarrà in standby in attesa del token...")
        while not TELEGRAM_BOT_TOKEN:
            time.sleep(10)
            load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
            TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
            
        print("✅ TELEGRAM_BOT_TOKEN rilevato! Avvio del bot...")
        
    run_telegram_loop(TELEGRAM_BOT_TOKEN)


if __name__ == "__main__":
    main()
