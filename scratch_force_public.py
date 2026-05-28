import os
import sys

# Aggiungi 'src' al path per gli import
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from newsica.utils.youtube_live_helper import force_live_stream_public

def main():
    cache_path = os.path.join(BASE_DIR, "tmp", "live_video_cache.txt")
    if not os.path.exists(cache_path):
        print(f"❌ Errore: Il file di cache '{cache_path}' non esiste.")
        sys.exit(1)

    with open(cache_path, "r", encoding="utf-8") as f:
        video_id = f.read().strip()

    if not video_id or len(video_id) != 11:
        print(f"❌ Errore: ID video '{video_id}' letto dalla cache non valido.")
        sys.exit(1)

    print(f"📡 ID live corrente individuato: {video_id}")
    print("⏳ Invio richiesta di switch privacy a PUBBLICO su YouTube...")
    
    result = force_live_stream_public(video_id)
    
    if result.get("status") == "success":
        print(f"🎉 SUCCESSO: {result.get('message')}")
    else:
        print(f"❌ ERRORE [{result.get('status')}]: {result.get('message')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
