import json
import os
import re
import sys
import time
from datetime import datetime

# Forza IPv4 per evitare i blocchi e i caricamenti infiniti IPv6 della VPS
import socket
_original_getaddrinfo = socket.getaddrinfo
def _patched_getaddrinfo(host, port, family=0, *args, **kwargs):
    return _original_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
socket.getaddrinfo = _patched_getaddrinfo

import requests
import pytchat
import pytchat.util
# Monkey-patch per evitare che la VPS venga bloccata dall'anti-bot di YouTube sulla watch page
pytchat.util.get_channelid = lambda client, video_id: "UCQOA9AoLRA8XG2g9ruogE1g"

from newsica.storage.repositories.ai_music_jobs_repository import enqueue_job
from newsica.audio.ai_music_runtime import launch_ai_music_worker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")

LIVE_VIDEO_ID_FILE = os.path.join(TMP_DIR, "live_video_id.txt")
LIVE_VIDEO_CACHE_FILE = os.path.join(TMP_DIR, "live_video_cache.txt")
PUBLIC_VERIFIED_VIDEO_ID_FILE = os.path.join(TMP_DIR, "public_verified_video_id.txt")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHAT_USE_API = os.getenv("YOUTUBE_CHAT_USE_API", "false").lower() == "true"
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UCQOA9AoLRA8XG2g9ruogE1g")
YOUTUBE_HANDLE = os.getenv("YOUTUBE_HANDLE", "@NewsicaTV")
YOUTUBE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}
YOUTUBE_COOKIES = {
    "CONSENT": "YES+cb.20210328-17-p0.it+FX+999"
}
YOUTUBE_API_QUOTA_COOLDOWN_SECONDS = 3600
youtube_api_quota_exceeded_until = 0.0

# Filtri di Moderazione
MAX_MSG_LENGTH = 90
USER_RATE_LIMIT_SECONDS = 15  # 15 secondi per utente
PROFANITY_BLACKLIST = {
    "cazzo", "vaffanculo", "stronzo", "stronza", "puttana", "troia", "merda", "coglion",
    "bastardo", "bastarda", "frocio", "finocchio", "negro", "terrone", "terroni", "troie"
}

user_last_message_time = {}

SUPPORTED_MUSIC_THEMES = {
    "rock": "rock",
    "rocknroll": "rock",
    "rock and roll": "rock",
    "dance": "dance/disco",
    "disco": "dance/disco",
    "dance disco": "dance/disco",
    "house": "dance/disco",
    "latin": "latin/reggaeton/dembow",
    "reggaeton": "latin/reggaeton/dembow",
    "dembow": "latin/reggaeton/dembow",
    "latino": "latin/reggaeton/dembow",
    "synthwave": "synthwave",
    "retrowave": "synthwave",
    "lofi": "lofi chill",
    "lo-fi": "lofi chill",
    "chill": "lofi chill",
    "lofi chill": "lofi chill",
    "ballad": "pop ballad",
    "ballata": "pop ballad",
    "pop ballad": "pop ballad",
}

MUSIC_REQUEST_PATTERNS = (
    "vorrei ascoltare",
    "voglio ascoltare",
    "mi fai ascoltare",
    "metti un brano",
    "metti una canzone",
    "metti un pezzo",
    "fammi sentire",
    "manda un brano",
    "riproduci un brano",
)


def _strip_music_request_lead_in(message: str) -> str:
    text = clean_text(message)
    if not text:
        return ""

    lowered = text.lower()
    matched_trigger = None
    for trigger in sorted(MUSIC_REQUEST_PATTERNS, key=len, reverse=True):
        idx = lowered.find(trigger)
        if idx != -1:
            matched_trigger = (idx, idx + len(trigger))
            break

    if matched_trigger:
        text = text[matched_trigger[1]:].strip(" ,:;-")

    text = re.sub(r"^(un|una)\s+(brano|canzone|pezzo|track)\b", "", text, flags=re.IGNORECASE).strip(" ,:;-")
    text = re.sub(r"^(musica|genere)\b", "", text, flags=re.IGNORECASE).strip(" ,:;-")
    return clean_text(text)


def clean_text(text):
    if not text:
        return ""
    return " ".join(text.strip().split())


def fetch_youtube_page(url):
    return requests.get(url, headers=YOUTUBE_HEADERS, cookies=YOUTUBE_COOKIES, timeout=10)


def inspect_live_video(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}&ucbcb=1"
    try:
        response = fetch_youtube_page(url)
        if response.status_code != 200:
            return {"is_live": False, "reason": f"HTTP {response.status_code}"}

        match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', response.text)
        if not match:
            return {"is_live": False, "reason": "player response non trovata"}

        data = json.loads(match.group(1))
        video_details = data.get("videoDetails", {})
        playability = data.get("playabilityStatus", {}) or {}
        microformat = data.get("microformat", {}).get("playerMicroformatRenderer", {}) or {}
        live_broadcast = microformat.get("liveBroadcastDetails", {}) or {}

        title = clean_text(video_details.get("title", ""))
        reason = clean_text(playability.get("reason", ""))
        reason_lc = reason.lower()
        ended_markers = (
            "terminat",
            "ended",
            "non è in diretta",
            "non e' in diretta",
            "not live",
            "offline",
        )

        if reason and any(marker in reason_lc for marker in ended_markers):
            return {"is_live": False, "reason": reason, "title": title}

        is_live = bool(video_details.get("isLive")) or bool(live_broadcast.get("isLiveNow"))
        if not is_live and '"isLiveNow":true' in response.text:
            is_live = True

        return {
            "is_live": is_live,
            "reason": reason,
            "title": title,
        }
    except Exception as e:
        return {"is_live": False, "reason": f"errore verifica watch page: {e}"}


def pick_live_video_id(candidate_ids, source_label):
    seen = set()
    first_candidate = None
    first_candidate_reason = None

    for video_id in candidate_ids:
        if not video_id or len(video_id) != 11 or video_id in seen:
            continue
        seen.add(video_id)

        if first_candidate is None:
            first_candidate = video_id

        info = inspect_live_video(video_id)
        if info.get("is_live"):
            print(f"✅ [DISCOVERY] Video live confermato da {source_label}: {video_id} ({info.get('title', 'titolo sconosciuto')})")
            return video_id

        reason = info.get("reason") or "video non live"
        if video_id == first_candidate:
            first_candidate_reason = reason
        print(f"ℹ️ [DISCOVERY] Scarto Video ID {video_id} da {source_label}: {reason}")

    # Fallback in caso di blocco anti-bot di YouTube
    if first_candidate:
        reason_lc = (first_candidate_reason or "").lower()
        if "accedi" in reason_lc or "confermare" in reason_lc or "bot" in reason_lc or "signin" in reason_lc or "sign in" in reason_lc:
            print(f"⚠️ [DISCOVERY] Ispezione video bloccata da anti-bot YouTube. Fallback sul primo ID candidato trovato: {first_candidate}")
            return first_candidate

    return None


def extract_music_request(message):
    cleaned_message = clean_text(message)
    normalized = cleaned_message.lower()
    if not normalized:
        return None

    if not any(trigger in normalized for trigger in MUSIC_REQUEST_PATTERNS):
        return None
    if not any(word in normalized for word in ("brano", "canzone", "pezzo", "musica", "track")):
        return None

    compact = normalized.replace("-", " ")
    theme = None
    for alias, canonical in sorted(SUPPORTED_MUSIC_THEMES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in compact:
            theme = canonical
            break

    custom_brief = _strip_music_request_lead_in(cleaned_message)

    return {
        "theme": theme,
        "custom_brief": custom_brief[:240] if custom_brief else "",
    }


def trigger_music_request_generation():
    try:
        launch_ai_music_worker()
    except Exception as e:
        print(f"❌ [CHAT REQUEST] Impossibile avviare il generatore musicale: {e}")


def maybe_enqueue_music_request(author, message, video_id):
    intent = extract_music_request(message)
    if not intent:
        return None

    import uuid
    from newsica.storage.repositories.chat_music_requests_repository import enqueue_request

    req_id = str(uuid.uuid4())[:8]
    prompt = intent.get("custom_brief") or message

    request = enqueue_request(
        id=req_id,
        video_id=video_id,
        author=author,
        prompt=prompt,
    )
    if not request:
        print(f"❌ [CHAT REQUEST] Errore nell'accodamento della richiesta nel database.")
        return None

    job, created = enqueue_job(
        job_type="chat_request",
        source="chat",
        request_id=request["id"],
        theme=intent.get("theme"),
        custom_brief=intent.get("custom_brief"),
        dedupe_key=request["id"],
    )
    print(
        f"🎵 [CHAT REQUEST] Richiesta musicale acquisita da {author}: "
        f"theme={intent.get('theme') or 'freeform'} | text='{message}'"
    )
    if created:
        print(f"🧾 [CHAT REQUEST] Job musica accodato: {job['id']}")
    else:
        print(f"ℹ️ [CHAT REQUEST] Job già presente: {job['id']}")
    trigger_music_request_generation()
    return request


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

    try:
        print(f"🔍 [DISCOVERY] Scansione della pagina live pubblica: {url}")
        r = fetch_youtube_page(url)
        if r.status_code == 200:
            candidate_ids = []

            # 1. Prova a cercare ytInitialPlayerResponse
            match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', r.text)
            if match:
                try:
                    data = json.loads(match.group(1))
                    video_details = data.get("videoDetails", {})
                    video_id = video_details.get("videoId")
                    if video_id:
                        candidate_ids.append(video_id)
                except Exception as je:
                    print(f"⚠️ [DISCOVERY] Errore parsing ytInitialPlayerResponse: {je}")

            # 2. Fallback: cerca canonical link
            canonical_match = re.search(r'<link rel="canonical" href="([^"]+)"', r.text)
            if canonical_match:
                v_match = re.search(r'v=([a-zA-Z0-9_-]{11})', canonical_match.group(1))
                if v_match:
                    candidate_ids.append(v_match.group(1))

            # 3. Fallback: cerca videoId generico
            video_ids = re.findall(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', r.text)
            if video_ids:
                candidate_ids.extend(video_ids[:8])

            return pick_live_video_id(candidate_ids, "pagina pubblica")
    except Exception as e:
        print(f"❌ [DISCOVERY] Errore nello scraping della pagina live: {e}")
    return None


def get_live_video_id_embed(channel_id):
    """
    Rileva l'ID del video live a costo zero usando l'embed url pubblico (fallback secondario).
    """
    url = f"https://www.youtube.com/embed/live_stream?channel={channel_id}"
    try:
        r = fetch_youtube_page(url)
        if r.status_code == 200:
            candidate_ids = []

            # Canonical link search
            canonical_match = re.search(r'<link rel="canonical" href="([^"]+)"', r.text)
            if canonical_match:
                v_match = re.search(r'v=([a-zA-Z0-9_-]{11})', canonical_match.group(1))
                if v_match:
                    candidate_ids.append(v_match.group(1))
            
            # JSON videoId search
            video_id_matches = re.findall(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', r.text)
            if video_id_matches:
                candidate_ids.extend(video_id_matches[:8])

            return pick_live_video_id(candidate_ids, "embed pubblico")
    except Exception as e:
        print(f"❌ [DISCOVERY] Errore nello scraping del video live ID embed: {e}")
    return None


def get_live_video_id_via_api(api_key, channel_id):
    """
    Usa la YouTube Data API per trovare il video live attuale del canale.
    Questa strategia e' piu' affidabile dello scraping della pagina pubblica
    quando il canale ha piu' live recenti con lo stesso titolo.
    """
    global youtube_api_quota_exceeded_until

    now = time.time()
    if youtube_api_quota_exceeded_until > now:
        remaining = int(youtube_api_quota_exceeded_until - now)
        print(f"⏸️ [DISCOVERY] YouTube API in cooldown per quota esaurita, skip per altri {remaining}s.")
        return None

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "eventType": "live",
        "type": "video",
        "maxResults": 1,
        "key": api_key,
    }
    try:
        print(f"🔍 [DISCOVERY] Scansione via YouTube Data API per il canale {channel_id}...")
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            if items:
                video_id = items[0].get("id", {}).get("videoId")
                if video_id and len(video_id) == 11:
                    print(f"✅ [DISCOVERY] Trovato Video Live ID via API: {video_id}")
                    return video_id
            print("⚠️ [DISCOVERY] Nessun video live trovato via API per il canale.")
        else:
            if r.status_code == 403 and "quotaExceeded" in r.text:
                youtube_api_quota_exceeded_until = time.time() + YOUTUBE_API_QUOTA_COOLDOWN_SECONDS
                print(f"⏸️ [DISCOVERY] Quota YouTube API esaurita. Sospendo le chiamate API per {YOUTUBE_API_QUOTA_COOLDOWN_SECONDS}s.")
            print(f"❌ [DISCOVERY] Errore search.list: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ [DISCOVERY] Errore nella ricerca API del video live: {e}")
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

    # 2. Se disponibile, usa la YouTube Data API per trovare il video live attuale.
    if YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID and YOUTUBE_CHAT_USE_API:
        v_id = get_live_video_id_via_api(YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID)
        if v_id:
            try:
                with open(LIVE_VIDEO_CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(v_id)
            except Exception:
                pass
            return v_id

    # 3. Usa l'auto-discovery basato sulla pagina live pubblica
    if YOUTUBE_HANDLE or YOUTUBE_CHANNEL_ID:
        v_id = get_live_video_id_from_public_page(YOUTUBE_HANDLE, YOUTUBE_CHANNEL_ID)
        if v_id:
            print(f"✅ [DISCOVERY] Trovato Video Live ID da pagina pubblica: {v_id}")
            try:
                with open(LIVE_VIDEO_CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(v_id)
            except Exception:
                pass
            return v_id

    # 4. Fallback all'auto-discovery basato su embed url
    if YOUTUBE_CHANNEL_ID:
        print(f"🔍 [DISCOVERY] Avvio scansione embed come fallback per il canale {YOUTUBE_CHANNEL_ID}...")
        v_id = get_live_video_id_embed(YOUTUBE_CHANNEL_ID)
        if v_id:
            print(f"✅ [DISCOVERY] Trovato Video Live ID da embed: {v_id}")
            try:
                with open(LIVE_VIDEO_CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(v_id)
            except Exception:
                pass
            return v_id

    # 5. Fallback a una cache automatica del video live precedente
    if os.path.exists(LIVE_VIDEO_CACHE_FILE):
        try:
            with open(LIVE_VIDEO_CACHE_FILE, "r", encoding="utf-8") as f:
                v_id = f.read().strip()
                if len(v_id) == 11:
                    info = inspect_live_video(v_id)
                    if info.get("is_live"):
                        print(f"✅ [DISCOVERY] Riutilizzo cache live confermata: {v_id}")
                        return v_id
                    print(f"ℹ️ [DISCOVERY] Cache live scartata ({v_id}): {info.get('reason') or 'video non live'}")
                    try:
                        os.remove(LIVE_VIDEO_CACHE_FILE)
                    except OSError:
                        pass
        except Exception:
            pass

    # 6. Controlla .env
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
    
    from newsica.storage.repositories.editorial_memory_repository import set_memory
    import json
    try:
        set_memory("latest_chat", json.dumps(data, ensure_ascii=False))
        print(f"💬 [LIVE CHAT] Scritto messaggio in DB di {author}: \"{message}\"")
    except Exception as e:
        print(f"❌ Errore nella scrittura di latest_chat in DB: {e}")


def run_api_loop(api_key, chat_id, video_id):
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
                                maybe_enqueue_music_request(author, message, video_id)
                            elif not is_moderated(author, message):
                                write_latest_chat(author, message, is_moderator=is_mod, is_owner=is_own, is_sponsor=is_spon)
                                maybe_enqueue_music_request(author, message, video_id)
                                
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
                        maybe_enqueue_music_request(author, message, video_id)
                    elif not is_moderated(author, message):
                        write_latest_chat(author, message, is_moderator=is_mod, is_owner=is_own, is_sponsor=is_spon)
                        maybe_enqueue_music_request(author, message, video_id)
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
        
        # Verifica ed effettua lo switch a PUBBLICO se non è già stato fatto per questa sessione live
        already_public = False
        if os.path.exists(PUBLIC_VERIFIED_VIDEO_ID_FILE):
            try:
                with open(PUBLIC_VERIFIED_VIDEO_ID_FILE, "r", encoding="utf-8") as f:
                    cached_verified = f.read().strip()
                    if cached_verified == video_id:
                        already_public = True
            except Exception:
                pass

        if not already_public:
            print(f"⏳ [CHAT AGENT] Rilevato nuovo ID video live '{video_id}' non verificato come pubblico. Tentativo di switch a PUBBLICO...")
            try:
                from newsica.utils.youtube_live_helper import force_live_stream_public
                result = force_live_stream_public(video_id)
                if result.get("status") == "success":
                    print(f"🎉 [CHAT AGENT] {result.get('message')}")
                    with open(PUBLIC_VERIFIED_VIDEO_ID_FILE, "w", encoding="utf-8") as f:
                        f.write(video_id)
                else:
                    print(f"⚠️ [CHAT AGENT] Impossibile impostare la live su pubblico [{result.get('status')}]: {result.get('message')}")
            except Exception as se:
                print(f"❌ [CHAT AGENT] Eccezione durante il tentativo di switch privacy live: {se}")

        # Tentativo di usare l'API ufficiale
        if YOUTUBE_API_KEY and YOUTUBE_CHAT_USE_API:
            print("🔑 [CHAT AGENT] Chiave API rilevata e abilitata in .env. Risoluzione liveChatId...")
            chat_id = get_active_live_chat_id(YOUTUBE_API_KEY, video_id)
            if chat_id:
                print(f"✅ [CHAT AGENT] Trovato activeLiveChatId: {chat_id}")
                success = run_api_loop(YOUTUBE_API_KEY, chat_id, video_id)
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
