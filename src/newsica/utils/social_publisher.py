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
        """Pubblica lo short su TikTok."""
        access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

        if not access_token:
            return {
                "status": "config_missing",
                "message": "Credenziali TikTok non configurate nel file .env (TIKTOK_ACCESS_TOKEN)."
            }
            
        log_decision("social_publisher", f"TikTok upload richiesto per {os.path.basename(video_path)} - Titolo: '{title}'")
        return {
            "status": "success",
            "message": "Caricamento simulato con successo su TikTok! (Dry-run attivo)"
        }
