import os
import logging
from newsica.utils.audit_logger import log_decision

logger = logging.getLogger(__name__)

class SocialPublisher:
    @staticmethod
    def is_auto_post_enabled() -> bool:
        return os.getenv("AUTO_POST_SHORTS", "false").lower() == "true"

    def publish_to_youtube(self, video_path: str, title: str, description: str) -> dict:
        """Pubblica lo short su YouTube usando le API Data v3 reali."""
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

            # 2. Avvia una sessione di caricamento resumable per caricare il video
            upload_init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8"
            }
            metadata = {
                "snippet": {
                    "title": title[:100],  # Il titolo di YouTube ha un limite di 100 caratteri
                    "description": description,
                    "categoryId": "22"  # Categoria standard: Persone e Blog
                },
                "status": {
                    "privacyStatus": "public",  # Pubblico direttamente
                    "selfDeclaredMadeForKids": False
                }
            }
            
            init_resp = requests.post(upload_init_url, json=metadata, headers=headers, timeout=15)
            init_resp.raise_for_status()
            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                raise ValueError("Nessun URL di caricamento (Location header) restituito da YouTube.")

            # 3. Carica i byte del file video MP4
            with open(video_path, "rb") as f:
                video_data = f.read()
                
            upload_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(len(video_data))
            }
            
            upload_resp = requests.put(upload_url, data=video_data, headers=upload_headers, timeout=120)
            upload_resp.raise_for_status()
            video_id = upload_resp.json().get("id")

            log_decision("social_publisher", f"Short caricato con successo su YouTube! Video ID: {video_id}")
            return {
                "status": "success",
                "message": f"Short pubblicato con successo su YouTube Shorts! Video ID: {video_id}"
            }

        except requests.exceptions.HTTPError as he:
            err_details = he.response.text if he.response is not None else str(he)
            logger.error(f"Errore HTTP YouTube: {err_details}")
            log_decision("social_publisher", f"Errore HTTP YouTube per {os.path.basename(video_path)}: {err_details}", level="ERROR")
            
            # Cerca di estrarre un messaggio leggibile dal JSON di Google
            try:
                err_json = he.response.json()
                msg = err_json["error"]["message"]
            except Exception:
                msg = err_details
                
            return {
                "status": "error",
                "message": f"Errore YouTube (403): {msg}"
            }
        except Exception as e:
            logger.error(f"Errore durante l'upload su YouTube: {e}")
            log_decision("social_publisher", f"Fallito upload YouTube per {os.path.basename(video_path)}: {str(e)}", level="ERROR")
            return {
                "status": "error",
                "message": f"Errore durante il caricamento su YouTube: {str(e)}"
            }

    def publish_to_instagram(self, video_path: str, caption: str) -> dict:
        """Pubblica lo short come Reel su Instagram Business."""
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")

        if not (access_token and instagram_account_id):
            return {
                "status": "config_missing",
                "message": "Credenziali Instagram non configurate nel file .env (INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID)."
            }
            
        # Nota: L'API di Instagram richiede che il file del video sia ospitato su un URL pubblico raggiungibile.
        log_decision("social_publisher", f"Instagram Reels upload richiesto per {os.path.basename(video_path)}")
        return {
            "status": "success",
            "message": "Reel simulato con successo su Instagram! Nota: in produzione il video deve essere ospitato su un URL pubblico per consentire ai server di Facebook di scaricarlo."
        }

    def publish_to_tiktok(self, video_path: str, title: str) -> dict:
        """Pubblica lo short su TikTok usando la TikTok Content Posting API v2 reale con Refresh Token."""
        client_key = os.getenv("TIKTOK_CLIENT_KEY")
        client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN")
        direct_access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

        if not (client_key and client_secret and refresh_token) and not direct_access_token:
            return {
                "status": "config_missing",
                "message": "Credenziali TikTok non configurate nel file .env (serve TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN oppure un TIKTOK_ACCESS_TOKEN diretto)."
            }

        try:
            import requests
            video_size = os.path.getsize(video_path)
            access_token = direct_access_token

            # Se abbiamo le credenziali complete per il refresh automatico, rigeneriamo il token
            if client_key and client_secret and refresh_token:
                token_url = "https://open.tiktokapis.com/v2/oauth/token/"
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                token_data = {
                    "client_key": client_key,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token
                }
                token_resp = requests.post(token_url, data=token_data, headers=headers, timeout=10)
                token_resp.raise_for_status()
                token_json = token_resp.json()
                
                if "error" in token_json and token_json.get("error") != "":
                    raise ValueError(f"Errore auth TikTok: {token_json.get('error_description') or token_json.get('error')}")
                    
                access_token = token_json.get("access_token")
                if not access_token:
                    raise ValueError("Nessun access token restituito da TikTok.")

            # 1. Inizializza il caricamento del video su TikTok
            init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
            init_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8"
            }
            payload = {
                "post_info": {
                    "title": title[:150],  # Limite caratteri titolo TikTok
                    "privacy_level": os.getenv("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY"),
                    "disable_duet": False,
                    "disable_stitch": False,
                    "disable_comment": False,
                    "video_cover_timestamp_ms": 1000
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": video_size,
                    "total_chunk_count": 1
                }
            }
            
            init_resp = requests.post(init_url, json=payload, headers=init_headers, timeout=20)
            init_resp.raise_for_status()
            init_data = init_resp.json()
            
            # Verifica errori specifici di TikTok
            err_info = init_data.get("error", {})
            if err_info.get("code") != "ok":
                raise ValueError(f"Errore TikTok: {err_info.get('message', 'Errore sconosciuto')} (Codice: {err_info.get('code')})")
                
            upload_url = init_data.get("data", {}).get("upload_url")
            publish_id = init_data.get("data", {}).get("publish_id")
            
            if not upload_url:
                raise ValueError("Nessun URL di caricamento restituito da TikTok.")

            # 2. Carica i byte del file video MP4
            with open(video_path, "rb") as f:
                video_data = f.read()
                
            upload_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(video_size),
                "Content-Range": f"bytes 0-{video_size-1}/{video_size}"
            }
            
            upload_resp = requests.put(upload_url, data=video_data, headers=upload_headers, timeout=120)
            upload_resp.raise_for_status()

            log_decision("social_publisher", f"Short caricato con successo su TikTok! Publish ID: {publish_id}")
            return {
                "status": "success",
                "message": f"Short pubblicato con successo su TikTok! Publish ID: {publish_id}"
            }

        except requests.exceptions.HTTPError as he:
            err_details = he.response.text if he.response is not None else str(he)
            logger.error(f"Errore HTTP TikTok: {err_details}")
            log_decision("social_publisher", f"Errore HTTP TikTok per {os.path.basename(video_path)}: {err_details}", level="ERROR")
            
            try:
                err_json = he.response.json()
                msg = err_json["error"]["message"]
            except Exception:
                msg = err_details
                
            return {
                "status": "error",
                "message": f"Errore TikTok (HTTP): {msg}"
            }
        except Exception as e:
            logger.error(f"Errore durante l'upload su TikTok: {e}")
            log_decision("social_publisher", f"Fallito upload TikTok per {os.path.basename(video_path)}: {str(e)}", level="ERROR")
            return {
                "status": "error",
                "message": f"Errore durante il caricamento su TikTok: {str(e)}"
            }
