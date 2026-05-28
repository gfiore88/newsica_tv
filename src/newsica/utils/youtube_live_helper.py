import os
import logging
from newsica.utils.audit_logger import log_decision

logger = logging.getLogger(__name__)

def force_live_stream_public(video_id: str) -> dict:
    """
    Cambia la privacy dell'attuale live stream a 'public' tramite OAuth 2.0.
    Utilizza le credenziali client e il refresh token definiti nel file .env.
    """
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    if not (client_id and client_secret and refresh_token):
        return {
            "status": "config_missing",
            "message": "Credenziali YouTube non configurate nel file .env (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN)."
        }

    try:
        import requests
        # 1. Scambia il refresh token con un access token fresco
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        token_resp = requests.post(token_url, data=token_data, timeout=10)
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise ValueError("Nessun access token restituito da Google.")

        # 2. Aggiorna lo stato della privacy a public
        update_url = "https://www.googleapis.com/youtube/v3/videos?part=status"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        payload = {
            "id": video_id,
            "status": {
                "privacyStatus": "public"
            }
        }
        
        resp = requests.put(update_url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        
        log_decision("youtube_live_helper", f"Privacy della live {video_id} modificata con successo in pubblica.")
        return {
            "status": "success",
            "message": f"Diretta {video_id} impostata con successo come PUBBLICA!"
        }

    except requests.exceptions.HTTPError as he:
        err_details = he.response.text if he.response is not None else str(he)
        logger.error(f"Errore HTTP YouTube durante switch privacy live: {err_details}")
        log_decision("youtube_live_helper", f"Errore HTTP YouTube per switch privacy della live {video_id}: {err_details}", level="ERROR")
        
        try:
            err_json = he.response.json()
            msg = err_json["error"]["message"]
        except Exception:
            msg = err_details
            
        return {
            "status": "error",
            "message": f"Errore YouTube: {msg}"
        }
    except Exception as e:
        logger.error(f"Errore durante lo switch privacy della live su YouTube: {e}")
        log_decision("youtube_live_helper", f"Fallito switch privacy YouTube per la live {video_id}: {str(e)}", level="ERROR")
        return {
            "status": "error",
            "message": f"Errore durante lo switch privacy: {str(e)}"
        }
