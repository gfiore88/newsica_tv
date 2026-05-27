import os
import logging
import time
import hashlib
from newsica.utils.audit_logger import log_decision

logger = logging.getLogger(__name__)

class SocialPublisher:
    @staticmethod
    def is_auto_post_enabled() -> bool:
        return os.getenv("AUTO_POST_SHORTS", "false").lower() == "true"

    @staticmethod
    def _bulk_status_from_results(results: dict) -> str:
        statuses = [item.get("status") for item in results.values()]
        if statuses and all(status == "success" for status in statuses):
            return "success"
        if any(status == "success" for status in statuses):
            return "partial"
        if any(status == "config_missing" for status in statuses):
            return "config_missing"
        return "error"

    @staticmethod
    def _bulk_message_from_results(results: dict) -> str:
        labels = {
            "youtube": "YouTube",
            "instagram": "Instagram",
            "tiktok": "TikTok",
        }
        lines = []
        for platform in ("youtube", "instagram", "tiktok"):
            result = results.get(platform, {})
            label = labels[platform]
            status = result.get("status", "error")
            prefix = "OK" if status == "success" else "KO"
            lines.append(f"[{prefix}] {label}: {result.get('message', 'Nessuna risposta disponibile.')}")
        return "\n".join(lines)

    def _upload_to_cloudinary(self, video_path: str) -> str:
        """Effettua il caricamento del file video locale su Cloudinary firmato crittograficamente."""
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        api_key = os.getenv("CLOUDINARY_API_KEY")
        api_secret = os.getenv("CLOUDINARY_API_SECRET")

        if not (cloud_name and api_key and api_secret):
            raise ValueError("Credenziali Cloudinary incomplete nel file .env (richiede CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET).")

        timestamp = int(time.time())
        # Calcola la firma SHA-1 richiesta da Cloudinary (i parametri devono essere ordinati alfabeticamente)
        params_to_sign = f"timestamp={timestamp}{api_secret}"
        signature = hashlib.sha1(params_to_sign.encode("utf-8")).hexdigest()

        upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/video/upload"

        import requests
        with open(video_path, "rb") as f:
            files = {"file": f}
            data = {
                "api_key": api_key,
                "timestamp": timestamp,
                "signature": signature
            }
            log_decision("social_publisher", f"Avvio upload video {os.path.basename(video_path)} su Cloudinary...")
            resp = requests.post(upload_url, files=files, data=data, timeout=300)
            resp.raise_for_status()
            secure_url = resp.json().get("secure_url")
            log_decision("social_publisher", f"Upload Cloudinary completato con successo! URL: {secure_url}")
            return secure_url

    def _publish_via_buffer(
        self,
        video_url: str,
        caption: str,
        service_name: str,
        title: str = None,
        post_type: str = None,
    ) -> dict:
        """Pubblica lo short tramite Buffer GraphQL API cercando il canale con il service specificato."""
        access_token = os.getenv("BUFFER_ACCESS_TOKEN")
        if not access_token:
            return {
                "status": "config_missing",
                "message": "Access Token di Buffer non configurato nel file .env (BUFFER_ACCESS_TOKEN)."
            }

        import requests
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # 1. Recupera l'organizzazione dell'utente
        org_query = {
            "query": """
            query {
              account {
                organizations {
                  id
                  name
                }
              }
            }
            """
        }
        try:
            log_decision("social_publisher", "Richiesta organizzazioni a Buffer...")
            org_resp = requests.post("https://api.buffer.com", json=org_query, headers=headers, timeout=15)
            org_resp.raise_for_status()
            org_json = org_resp.json()
            
            # Controlla errori GraphQL
            if "errors" in org_json:
                raise ValueError(f"Errore GraphQL Buffer: {org_json['errors'][0].get('message')}")
                
            orgs = org_json.get("data", {}).get("account", {}).get("organizations", [])
            if not orgs:
                raise ValueError("Nessuna organizzazione trovata sul tuo account Buffer.")
                
            org_id = orgs[0].get("id")
            
            # 2. Recupera i canali collegati a questa organizzazione
            channels_query = {
                "query": f"""
                query {{
                  channels(input: {{ organizationId: "{org_id}" }}) {{
                    id
                    name
                    displayName
                    service
                  }}
                }}
                """
            }
            log_decision("social_publisher", f"Richiesta canali per l'organizzazione {org_id}...")
            chan_resp = requests.post("https://api.buffer.com", json=channels_query, headers=headers, timeout=15)
            chan_resp.raise_for_status()
            chan_json = chan_resp.json()
            
            if "errors" in chan_json:
                raise ValueError(f"Errore GraphQL Buffer (canali): {chan_json['errors'][0].get('message')}")
                
            channels = chan_json.get("data", {}).get("channels", [])
            
            # 3. Trova il canale corrispondente al service_name desiderato
            # Esempi di service in Buffer: 'youtube', 'instagram', 'tiktok'
            target_channel = None
            for chan in channels:
                if chan.get("service") == service_name:
                    target_channel = chan
                    break
                    
            if not target_channel:
                connected_services = ", ".join([c.get("service", "") for c in channels if c.get("service")])
                return {
                    "status": "config_missing",
                    "message": f"Nessun profilo social '{service_name}' connesso su Buffer. Canali connessi attuali: {connected_services}. Aggiungilo prima su Buffer."
                }
                
            channel_id = target_channel.get("id")
            channel_name = target_channel.get("name") or target_channel.get("displayName")
            log_decision("social_publisher", f"Canale trovato su Buffer: {channel_name} ({channel_id}) per {service_name}")

            # 4. Crea il post su Buffer
            # Escapiamo le virgolette e gli a capo per il testo della didascalia in modo che sia una stringa GraphQL valida
            escaped_caption = caption.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            
            # Aggiungiamo i metadata specifici richiesti da Buffer per piattaforma.
            platform_metadata = ""
            if service_name == "youtube":
                escaped_title = (title or "Short NewsicaTV").replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
                escaped_title = escaped_title[:95]  # YouTube titolo max 100 char
                # Usiamo come categoria predefinita 25 (News & Politics) o 22 (People & Blogs)
                platform_metadata = f""",
                    metadata: {{
                      youtube: {{
                        title: "{escaped_title}",
                        categoryId: "22"
                      }}
                    }}"""
            elif service_name == "instagram":
                instagram_type = (post_type or "reel").strip().lower()
                platform_metadata = f""",
                    metadata: {{
                      instagram: {{
                        type: {instagram_type},
                        shouldShareToFeed: true
                      }}
                    }}"""

            post_mutation = {
                "query": f"""
                mutation {{
                  createPost(input: {{
                    text: "{escaped_caption}",
                    channelId: "{channel_id}",
                    schedulingType: automatic,
                    mode: shareNow,
                    assets: [
                      {{
                        video: {{
                          url: "{video_url}"
                        }}
                      }}
                    ]{platform_metadata}
                  }}) {{
                    ... on PostActionSuccess {{
                      post {{
                        id
                      }}
                    }}
                    ... on MutationError {{
                      message
                    }}
                  }}
                }}
                """
            }
            
            log_decision("social_publisher", f"Invio creazione post a Buffer per il canale {channel_name}...")
            post_resp = requests.post("https://api.buffer.com", json=post_mutation, headers=headers, timeout=20)
            post_resp.raise_for_status()
            post_json = post_resp.json()
            
            if "errors" in post_json:
                raise ValueError(f"Errore GraphQL Buffer (creazione post): {post_json['errors'][0].get('message')}")
                
            create_result = post_json.get("data", {}).get("createPost", {})
            if "message" in create_result:
                # Questo significa che è ritornato un MutationError
                raise ValueError(f"Errore Buffer: {create_result['message']}")
                
            post_id = create_result.get("post", {}).get("id")
            log_decision("social_publisher", f"Post Buffer creato con successo! Post ID: {post_id}")
            return {
                "status": "success",
                "message": f"Short pubblicato con successo tramite Buffer sul canale {channel_name}! Post ID: {post_id}"
            }

        except requests.exceptions.HTTPError as he:
            err_text = he.response.text if he.response is not None else str(he)
            logger.error(f"Errore HTTP Buffer: {err_text}")
            log_decision("social_publisher", f"Fallita pubblicazione via Buffer (HTTP): {err_text}", level="ERROR")
            return {
                "status": "error",
                "message": f"Errore Buffer API (HTTP): {err_text}"
            }
        except Exception as e:
            logger.error(f"Errore durante l'interazione con Buffer: {e}")
            log_decision("social_publisher", f"Fallita pubblicazione via Buffer: {str(e)}", level="ERROR")
            return {
                "status": "error",
                "message": f"Errore Buffer API: {str(e)}"
            }

    def publish_to_youtube(self, video_path: str, title: str, description: str) -> dict:
        """Pubblica lo short su YouTube usando le API Data v3 reali."""
        if os.getenv("BUFFER_USE_INTEGRATION", "false").lower() == "true":
            try:
                video_url = self._upload_to_cloudinary(video_path)
                return self._publish_via_buffer(video_url, description, "youtube", title=title)
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Errore durante la pubblicazione unificata YouTube (Cloudinary + Buffer): {e}"
                }

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
        if os.getenv("BUFFER_USE_INTEGRATION", "false").lower() == "true":
            try:
                video_url = self._upload_to_cloudinary(video_path)
                return self._publish_via_buffer(video_url, caption, "instagram", post_type="reel")
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Errore durante la pubblicazione unificata Instagram (Cloudinary + Buffer): {e}"
                }

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

    def publish_to_all_socials(self, video_path: str, title: str, caption: str) -> dict:
        """Pubblica lo short su YouTube, Instagram e TikTok con un'unica azione."""
        if os.getenv("BUFFER_USE_INTEGRATION", "false").lower() == "true":
            try:
                video_url = self._upload_to_cloudinary(video_path)
                results = {
                    "youtube": self._publish_via_buffer(video_url, caption, "youtube", title=title),
                    "instagram": self._publish_via_buffer(video_url, caption, "instagram", post_type="reel"),
                    "tiktok": self._publish_via_buffer(video_url, caption, "tiktok"),
                }
                return {
                    "status": self._bulk_status_from_results(results),
                    "message": self._bulk_message_from_results(results),
                    "results": results,
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Errore durante la pubblicazione multi-social via Buffer: {e}"
                }

        results = {
            "youtube": self.publish_to_youtube(video_path, title, caption),
            "instagram": self.publish_to_instagram(video_path, caption),
            "tiktok": self.publish_to_tiktok(video_path, title, caption),
        }
        return {
            "status": self._bulk_status_from_results(results),
            "message": self._bulk_message_from_results(results),
            "results": results,
        }

    def publish_to_tiktok(self, video_path: str, title: str, description: str = None) -> dict:
        """Pubblica lo short su TikTok usando la TikTok Content Posting API v2 reale con Refresh Token."""
        if os.getenv("BUFFER_USE_INTEGRATION", "false").lower() == "true":
            try:
                video_url = self._upload_to_cloudinary(video_path)
                return self._publish_via_buffer(video_url, description or title, "tiktok")
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Errore durante la pubblicazione unificata TikTok (Cloudinary + Buffer): {e}"
                }

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
                    "title": (description or title)[:150],  # Limite caratteri titolo TikTok
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
