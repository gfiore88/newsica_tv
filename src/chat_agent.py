import json
import os
import re
import sys
import time
from datetime import datetime
import requests
import pytchat

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")

LIVE_VIDEO_ID_FILE = os.path.join(TMP_DIR, "live_video_id.txt")
LATEST_CHAT_FILE = os.path.join(TMP_DIR, "latest_chat.json")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UCQOA9AoLRA8XG2g9ruogE1g")
YOUTUBE_HANDLE = os.getenv("YOUTUBE_HANDLE", "@NewsicaTV")

# Filtri di Moderazione
MAX_MSG_LENGTH = 90
USER_RATE_LIMIT_SECONDS = 180  # 3 minuti per utente
PROFANITY_BLACKLIST = {
    "cazzo", "vaffanculo", "stronzo", "stronza", "puttana", "troia", "merda", "coglion",
    "bastardo", "bastarda", "frocio", "finocchio", "negro", "terrone", "terroni", "troie"
}

user_last_message_time = {}


def clean_text(text):
    if not text:
        return ""
    return " ".join(text.strip().split())


def is_moderated(author, message):
    msg_clean = message.lower()
    
    # 1. Lunghezza massima
    if len(message) > MAX_MSG_LENGTH:
        print(f"⚠️ [MOD] Messaggio da {author} scartato (troppo lungo: {len(message)} caratteri)")
        return True
        
    # 2. Profanity filter
    for word in PROFANITY_BLACKLIST:
        if word in msg_clean:
            print(f"⚠️ [MOD] Messaggio da {author} scartato (contiene termine vietato: '{word}')")
            return True
            
    # 3. Rate limiting per utente
    now = time.time()
    if author in user_last_message_time:
        elapsed = now - user_last_message_time[author]
        if elapsed < USER_RATE_LIMIT_SECONDS:
            remaining = int(USER_RATE_LIMIT_SECONDS - elapsed)
            print(f"⚠️ [MOD] Messaggio da {author} limitato (rate limit attivo, mancano {remaining}s)")
            return True
            
    user_last_message_time[author] = now
    return False


def get_live_video_id_from_public_page(handle=None, channel_id=None):
    """
    Rileva l'ID del video live a costo zero usando la pagina live pubblica del canale.
    """
    if handle:
        url = f"https://www.youtube.com/{handle}/live?ucbcb=1"
    elif channel_id:
        url = f"https://www.youtube.com/channel/{channel_id}/live?ucbcb=1"
    else:
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    }
    cookies = {
        "CONSENT": "YES+cb.20210328-17-p0.it+FX+999"
    }
    try:
        print(f"🔍 [DISCOVERY] Scansione della pagina live pubblica: {url}")
        r = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        if r.status_code == 200:
            # 1. Prova a cercare ytInitialPlayerResponse
            match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', r.text)
            if match:
                try:
                    data = json.loads(match.group(1))
                    video_details = data.get("videoDetails", {})
                    video_id = video_details.get("videoId")
                    is_live = video_details.get("isLive", False)
                    if video_id and is_live:
                        print(f"✅ [DISCOVERY] Trovato Video ID {video_id} in ytInitialPlayerResponse (isLive={is_live})")
                        return video_id
                except Exception as je:
                    print(f"⚠️ [DISCOVERY] Errore parsing ytInitialPlayerResponse: {je}")

            # 2. Fallback: cerca canonical link
            canonical_match = re.search(r'<link rel="canonical" href="([^"]+)"', r.text)
            if canonical_match:
                v_match = re.search(r'v=([a-zA-Z0-9_-]{11})', canonical_match.group(1))
                if v_match:
                    print(f"✅ [DISCOVERY] Trovato Video ID {v_match.group(1)} in canonical link")
                    return v_match.group(1)

            # 3. Fallback: cerca videoId generico
            video_ids = re.findall(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', r.text)
            if video_ids:
                print(f"✅ [DISCOVERY] Trovato primo Video ID {video_ids[0]} in JSON generico")
                return video_ids[0]
    except Exception as e:
        print(f"❌ [DISCOVERY] Errore nello scraping della pagina live: {e}")
    return None


def get_live_video_id_embed(channel_id):
    """
    Rileva l'ID del video live a costo zero usando l'embed url pubblico (fallback secondario).
    """
    url = f"https://www.youtube.com/embed/live_stream?channel={channel_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            # Canonical link search
            canonical_match = re.search(r'<link rel="canonical" href="([^"]+)"', r.text)
            if canonical_match:
                v_match = re.search(r'v=([a-zA-Z0-9_-]{11})', canonical_match.group(1))
                if v_match:
                    return v_match.group(1)
            
            # JSON videoId search
            video_id_matches = re.findall(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', r.text)
            if video_id_matches:
                return video_id_matches[0]
    except Exception as e:
        print(f"❌ [DISCOVERY] Errore nello scraping del video live ID embed: {e}")
    return None


def get_active_video_id():
    # 1. Controlla se c'è un override manuale scritto su file
    if os.path.exists(LIVE_VIDEO_ID_FILE):
        try:
            with open(LIVE_VIDEO_ID_FILE, "r", encoding="utf-8") as f:
                v_id = f.read().strip()
                if len(v_id) == 11:
                    return v_id
        except Exception:
            pass

    # 2. Usa l'auto-discovery basato sulla pagina live pubblica (più affidabile)
    if YOUTUBE_HANDLE or YOUTUBE_CHANNEL_ID:
        v_id = get_live_video_id_from_public_page(YOUTUBE_HANDLE, YOUTUBE_CHANNEL_ID)
        if v_id:
            print(f"✅ [DISCOVERY] Trovato Video Live ID da pagina pubblica: {v_id}")
            try:
                with open(LIVE_VIDEO_ID_FILE, "w", encoding="utf-8") as f:
                    f.write(v_id)
            except Exception:
                pass
            return v_id

    # 3. Fallback all'auto-discovery basato su embed url
    if YOUTUBE_CHANNEL_ID:
        print(f"🔍 [DISCOVERY] Avvio scansione embed come fallback per il canale {YOUTUBE_CHANNEL_ID}...")
        v_id = get_live_video_id_embed(YOUTUBE_CHANNEL_ID)
        if v_id:
            print(f"✅ [DISCOVERY] Trovato Video Live ID da embed: {v_id}")
            try:
                with open(LIVE_VIDEO_ID_FILE, "w", encoding="utf-8") as f:
                    f.write(v_id)
            except Exception:
                pass
            return v_id

    # 4. Controlla .env
    v_id = os.getenv("YOUTUBE_LIVE_VIDEO_ID")
    if v_id and len(v_id) == 11:
        return v_id

    return None


def get_active_live_chat_id(api_key, video_id):
    """
    Usa videos.list per ottenere l'activeLiveChatId (costo quota: 1)
    """
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "liveStreamingDetails",
        "id": video_id,
        "key": api_key
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            if items:
                details = items[0].get("liveStreamingDetails", {})
                chat_id = details.get("activeLiveChatId")
                if chat_id:
                    return chat_id
                else:
                    print("⚠️ [API] La liveStreamingDetails non contiene un activeLiveChatId. La live potrebbe essere terminata.")
            else:
                print(f"⚠️ [API] Nessun video trovato per l'ID: {video_id}")
        else:
            print(f"❌ [API] Errore in videos.list: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ [API] Eccezione in get_active_live_chat_id: {e}")
    return None


def write_latest_chat(author, message, is_moderator=False, is_owner=False, is_sponsor=False):
    data = {
        "author": author,
        "message": message,
        "timestamp": time.time(),
        "is_moderator": is_moderator,
        "is_owner": is_owner,
        "is_sponsor": is_sponsor
    }
    try:
        with open(LATEST_CHAT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💬 [LIVE CHAT] Scritto messaggio di {author}: \"{message}\"")
    except Exception as e:
        print(f"❌ Errore nella scrittura di latest_chat.json: {e}")


def run_api_loop(api_key, chat_id):
    print("🚀 [CHAT AGENT] Avvio loop di lettura chat tramite YouTube Data API v3.")
    url = "https://www.googleapis.com/youtube/v3/liveChat/messages"
    next_page_token = None
    
    # Per non mostrare una marea di vecchi messaggi all'avvio, ignoriamo i messaggi con timestamp precedente a ora
    startup_time = datetime.utcnow()
    
    while True:
        params = {
            "liveChatId": chat_id,
            "part": "snippet,authorDetails",
            "key": api_key,
            "maxResults": 100
        }
        if next_page_token:
            params["pageToken"] = next_page_token
            
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                next_page_token = data.get("nextPageToken")
                polling_interval = data.get("pollingIntervalMillis", 5000) / 1000.0
                
                # Assicuriamoci che il polling sia sano (minimo 3 secondi)
                polling_interval = max(3.0, polling_interval)
                
                items = data.get("items", [])
                for item in items:
                    snippet = item.get("snippet", {})
                    author_details = item.get("authorDetails", {})
                    
                    published_str = snippet.get("publishedAt", "")
                    # YouTube restituisce ISO con Z o offset. Proviamo a parsare.
                    try:
                        # Rimuoviamo Z e limitiamo a 19 chars per semplicità
                        clean_pub = published_str.replace("Z", "")[:19]
                        pub_dt = datetime.strptime(clean_pub, "%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        pub_dt = startup_time
                        
                    # Elaboriamo solo se il messaggio è nuovo rispetto a startup_time o se non è la prima pagina
                    # (Se non abbiamo nextPageToken all'inizio, è la prima pagina di caricamento)
                    if not next_page_token or pub_dt >= startup_time:
                        author = author_details.get("displayName", "Anonimo")
                        message = snippet.get("displayMessage", "")
                        
                        is_mod = author_details.get("isChatModerator", False)
                        is_own = author_details.get("isChatOwner", False)
                        is_spon = author_details.get("isChatSponsor", False)
                        
                        message = clean_text(message)
                        if message:
                            # Se è il proprietario o moderatore, bypassiamo filtri di moderazione
                            if is_own or is_mod:
                                write_latest_chat(author, message, is_moderator=is_mod, is_owner=is_own, is_sponsor=is_spon)
                            elif not is_moderated(author, message):
                                write_latest_chat(author, message, is_moderator=is_mod, is_owner=is_own, is_sponsor=is_spon)
                                
                time.sleep(polling_interval)
            elif r.status_code == 403:
                # Quota superata o errore di autorizzazione
                print(f"❌ [API] Errore 403 (Quota esaurita o chiave non valida). Riavvio in modalità fallback pytchat in 5s...")
                time.sleep(5)
                return False
            else:
                print(f"⚠️ [API] Errore HTTP {r.status_code}: {r.text}. Riprovo in 10s...")
                time.sleep(10)
        except Exception as e:
            print(f"❌ [API] Eccezione nel loop API: {e}. Riprovo in 10s...")
            time.sleep(10)


def run_pytchat_loop(video_id):
    print("🚀 [CHAT AGENT] Avvio loop di lettura chat tramite fallback pytchat.")
    try:
        chat = pytchat.create(video_id=video_id)
    except Exception as e:
        print(f"❌ [PYTCHAT] Impossibile avviare pytchat: {e}")
        return
        
    while chat.is_alive():
        try:
            for c in chat.get().sync_items():
                author = c.author.name
                message = clean_text(c.message)
                
                is_mod = c.author.isChatModerator
                is_own = c.author.isChatOwner
                is_spon = c.author.isChatSponsor
                
                if message:
                    if is_own or is_mod:
                        write_latest_chat(author, message, is_moderator=is_mod, is_owner=is_own, is_sponsor=is_spon)
                    elif not is_moderated(author, message):
                        write_latest_chat(author, message, is_moderator=is_mod, is_owner=is_own, is_sponsor=is_spon)
            time.sleep(1)
        except Exception as e:
            print(f"❌ [PYTCHAT] Eccezione nel loop: {e}")
            time.sleep(5)
            
    print("⚠️ [PYTCHAT] La chat di pytchat si è interrotta. Possibile cambio video o disconnessione.")


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


def main():
    lock = check_singleton("chat_agent")
    if not lock:
        sys.exit(1)
        
    print("🎬 Chat Agent avviato.")
    os.makedirs(TMP_DIR, exist_ok=True)
    
    while True:
        video_id = get_active_video_id()
        if not video_id:
            print("💤 [CHAT AGENT] Nessun ID video live attivo trovato. Riprovo la ricerca tra 30 secondi...")
            time.sleep(30)
            continue
            
        print(f"🎯 [CHAT AGENT] Trovata sessione live attiva con ID: {video_id}")
        
        # Tentativo di usare l'API ufficiale
        if YOUTUBE_API_KEY:
            print("🔑 [CHAT AGENT] Chiave API rilevata in .env. Risoluzione liveChatId...")
            chat_id = get_active_live_chat_id(YOUTUBE_API_KEY, video_id)
            if chat_id:
                print(f"✅ [CHAT AGENT] Trovato activeLiveChatId: {chat_id}")
                success = run_api_loop(YOUTUBE_API_KEY, chat_id)
                if success is not False:
                    # Se esce con successo, o errore temporaneo, ripartiamo da capo
                    time.sleep(10)
                    continue
            else:
                print("⚠️ [CHAT AGENT] Impossibile recuperare activeLiveChatId via API (canale offline?).")
                
        # Se l'API non è disponibile, fallisce o non c'è la chiave, usiamo pytchat
        print("🔗 [CHAT AGENT] Utilizzo della modalità di fallback pytchat...")
        run_pytchat_loop(video_id)
        
        print("🔄 [CHAT AGENT] Loop terminato, attesa 15s prima di riprovare...")
        time.sleep(15)


if __name__ == "__main__":
    main()
