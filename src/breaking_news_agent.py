import os
import sys
import time
import argparse
import subprocess

import requests
import re
from newsica.domain.characters import get_character
from newsica.editorial.gravity_assessor import assess_news_gravity
from newsica.generation.tts_jobs import remote_generation_enabled

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
JINGLES_DIR = os.path.join(BASE_DIR, "assets", "jingles")
BREAKING_JINGLE_FILE = os.path.join(JINGLES_DIR, "jingle_breaking_news.mp3")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
FFMPEG_CMD = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg") else "ffmpeg"
LAST_BREAKING_FILE = os.path.join(TMP_DIR, "last_breaking_news.txt")

def generate_breaking_news(force=True):
    print("🚨 Avvio pipeline Breaking News...")
    character = get_character("breaking_news")
    
    # 1. Recupero la prima notizia di ultimora dal DB
    from newsica.storage.repositories.news_articles_repository import get_recent_articles
    notizia = None
    try:
        news_items = get_recent_articles(limit=50)
        for item in news_items:
            # L'attributo source nel DB al momento è salvato se passiamo il dictionary.
            # get_recent_articles restituisce {title, description, publishedAt}
            # Se vogliamo controllare 'ansa_ultimora', possiamo controllare il testo o il titolo
            # oppure dovremmo salvare il 'source'. Mappiamo source = category per semplicità.
            if "ultimora" in item.get("title", "").lower() or "ultim'ora" in item.get("title", "").lower() or item.get("is_breaking") == 1:
                notizia = item
                # Rinominiano description in summary per la retrocompatibilità
                notizia["summary"] = notizia.get("description", "")
                break
    except Exception as e:
        print(f"⚠️ Errore nel caricamento delle news da DB: {e}")

    if not notizia:
        if force:
            print("⚠️ Nessuna notizia ANSA ultim'ora disponibile. Procedo solo per esecuzione forzata/manuale.")
        else:
            print("⏩ [Daemon] Nessuna notizia ANSA ultim'ora disponibile. Nessuna breaking news generata.")
            return False
            
    # Testo di fallback drammatico
    testo_default = (
        "Interrompiamo le trasmissioni per un'Edizione Straordinaria. "
        "Un evento di eccezionale importanza è stato appena battuto dalle agenzie di stampa nazionale. "
        "Tutti i dettagli e le ripercussioni sul nostro portale. Restate sintonizzati su Newsica TV per tutti gli aggiornamenti in tempo reale."
    )
    
    testo = testo_default
    
    severity_score = 0
    reason = "Valutazione di default"
    
    if notizia:
        titolo = notizia.get("title", "")
        sintesi = notizia.get("summary", "")
        news_text = f"TITOLO: {titolo}\nSINTESI: {sintesi}"
        print(f"📰 Notizia di ultim'ora selezionata: {titolo}")
        
        # Valuta la gravità della notizia
        try:
            severity_score, is_emergency, reason = assess_news_gravity(titolo, sintesi, "news")
            print(f"📊 [BreakingNewsAgent] Gravità: {severity_score}/100 | Emergenza: {is_emergency} | Motivo: {reason}")
        except Exception as e:
            print(f"⚠️ Errore nella valutazione della gravità: {e}")
            severity_score = 30
            reason = "Errore valutazione"
            
        # Forza la gravità da variabile d'ambiente per agevolare il testing
        force_severity = os.getenv("FORCE_SEVERITY")
        if force_severity:
            severity_score = int(force_severity)
            reason = "Test forzato di Edizione Straordinaria"
            print(f"🚨 [Test] Forza gravità a: {severity_score}")
            is_emergency = severity_score >= 90
            
        if not force and not is_emergency:
            print(f"⏩ [Daemon] La notizia non è una vera emergenza (Score {severity_score}). Ignoro.")
            return False
            
        # Controllo anti-duplicati nel demone
        if not force:
            if os.path.exists(LAST_BREAKING_FILE):
                with open(LAST_BREAKING_FILE, "r") as f:
                    last_title = f.read().strip()
                if last_title == titolo:
                    print("⏩ [Daemon] Notizia già trasmessa come Breaking News. Ignoro.")
                    return False
        
        # 2. Rielaborazione testo tramite LLM (Ollama locale)
        OLLAMA_URL = "http://localhost:11434/api/generate"
        MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:12b")
        SYSTEM_PROMPT = character.read_prompt()
        
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

    if remote_generation_enabled():
        from newsica.storage.repositories.generation_jobs_repository import enqueue_job

        job, created = enqueue_job(
            "breaking_news",
            priority=250,
            title="Breaking News",
            dedupe_key=f"breaking_news:{notizia.get('title') if notizia else 'manual'}:{int(time.time() // 300)}",
            payload={
                "text": testo,
                "severity_score": severity_score,
                "reason": reason,
                "character": character.id,
                "speed": character.speed,
                "jingle_path": character.jingle_path or BREAKING_JINGLE_FILE,
                "source": "manual" if force else "daemon",
            },
        )
        print(f"📡 Breaking News remota accodata: job={job.get('id')} created={created}")
        if notizia:
            with open(LAST_BREAKING_FILE, "w") as f:
                f.write(notizia.get("title", ""))
        return True
    
    # 4. Sintesi Vocale del Copione
    print("🎙️ Sintesi vocale tramite Kokoro AI...")
    voice_audio = os.path.join(TMP_DIR, "voice_breaking.wav")
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf

        # Carichiamo i file ONNX e bin dalla cartella principale del progetto
        onnx_path = os.path.join(BASE_DIR, "kokoro-v1.0.onnx")
        voices_path = os.path.join(BASE_DIR, "voices-v1.0.bin")
        kokoro = Kokoro(onnx_path, voices_path)
        
        from newsica.utils.voice_helper import get_voice_style_for_character
        voice_style = get_voice_style_for_character(kokoro, character.id)
        
        samples, sample_rate = kokoro.create(testo, voice=voice_style, speed=character.speed, lang="it")
        sf.write(voice_audio, samples, sample_rate)
        print("✅ Voce Breaking News generata con successo.")
    except Exception as e:
        print(f"❌ Errore durante Kokoro TTS: {e}")
        # Fallback a None
        voice_audio = None
        
    # 5. Preparazione jingle di apertura breaking news
    print("🔔 Preparazione jingle breaking news...")
    alarm_audio = os.path.join(TMP_DIR, "alarm_jingle.wav")
    breaking_jingle = character.jingle_path or BREAKING_JINGLE_FILE
    if os.path.exists(breaking_jingle):
        print(f"🎶 Uso jingle breaking news: {os.path.basename(breaking_jingle)}")
        subprocess.run([
            FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "error",
            "-i", breaking_jingle,
            "-ar", "24000", "-ac", "1", alarm_audio
        ], check=True)
    else:
        print("⚠️ Jingle breaking news non trovato, genero allarme fallback.")
        subprocess.run([
            FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=850:duration=0.5",
            "-f", "lavfi", "-i", "sine=frequency=0:duration=0.2",
            "-f", "lavfi", "-i", "sine=frequency=850:duration=0.5",
            "-f", "lavfi", "-i", "sine=frequency=0:duration=0.2",
            "-f", "lavfi", "-i", "sine=frequency=850:duration=0.8",
            "-filter_complex", "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1",
            "-ar", "24000", "-ac", "1", alarm_audio
        ], check=True)
    
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
    cmd = f"BREAKING_NEWS_READY|{bn_audio}|{severity_score}|{reason}"
    with open(CONTROL_FILE, "w") as f:
        f.write(cmd)
        
    if notizia:
        with open(LAST_BREAKING_FILE, "w") as f:
            f.write(notizia.get("title", ""))
            
    print("✅ Breaking News completa. Segnale pronto inviato al regista.")
    return True

def run_daemon():
    print("🕵️‍♂️ [Daemon] Agente Breaking News Autonomo avviato. Controllo ogni 15 minuti...")
    from newsica.storage.repositories.news_articles_repository import save_articles
    
    while True:
        try:
            print("⏳ [Daemon] Avvio ciclo di controllo ultim'ora...")
            
            print("🔄 [Daemon] Aggiornamento feed (collector)...")
            try:
                from newsica.sources.collector import collect_news_items
                all_news = collect_news_items()
                save_articles(all_news, category="news", is_breaking=False)
                print(f"✅ [Daemon] Cache aggiornata con {len(all_news)} notizie nel database.")
            except ImportError:
                print("⚠️ [Daemon] Impossibile importare collector, salto l'aggiornamento.")
            except Exception as e:
                print(f"⚠️ [Daemon] Errore nell'aggiornamento cache: {e}")
                
            # Esegue la logica senza forzatura manuale
            generate_breaking_news(force=False)
            
        except Exception as e:
            print(f"⚠️ [Daemon] Errore nel loop: {e}")
            
        print("💤 [Daemon] Riposo per 15 minuti...")
        time.sleep(900)

_singleton_lock = None

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true", help="Avvia l'agente in modalità demone (background)")
    args = parser.parse_args()
    
    if args.daemon:
        if not check_singleton("breaking_news_daemon"):
            print("❌ Demone già in esecuzione. Esco.")
            sys.exit(1)
        run_daemon()
    else:
        # Esecuzione manuale one-shot (non usa lo stesso singleton del demone, permette overlay)
        generate_breaking_news(force=True)
