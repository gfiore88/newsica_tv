import requests
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class HttpAiMusicBackend:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    def get_next_pending_job(self) -> dict | None:
        try:
            res = requests.post(f"{self.base_url}/api/ai_music_jobs/claim", timeout=10)
            res.raise_for_status()
            data = res.json()
            return data.get("job")
        except Exception as e:
            logger.debug("Nessun job pending o errore HTTP: %s", e)
            return None

    def mark_running(self, job_id: str) -> None:
        try:
            res = requests.post(f"{self.base_url}/api/ai_music_jobs/{job_id}/running", timeout=10)
            res.raise_for_status()
        except Exception as e:
            logger.error("Errore mark_running: %s", e)

    def mark_failed(self, job_id: str, error: str) -> None:
        try:
            res = requests.post(
                f"{self.base_url}/api/ai_music_jobs/{job_id}/failed",
                json={"error": error},
                timeout=10
            )
            res.raise_for_status()
        except Exception as e:
            logger.error("Errore mark_failed: %s", e)

    def mark_done(self, job_id: str, audio_path: str, title: str) -> None:
        try:
            file_path = Path(audio_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File non trovato: {audio_path}")

            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "audio/wav")}
                data = {"title": title}
                res = requests.post(
                    f"{self.base_url}/api/ai_music_jobs/{job_id}/artifact",
                    files=files,
                    data=data,
                    timeout=300
                )
            res.raise_for_status()
            logger.info("Upload %s completato con successo.", file_path.name)
        except Exception as e:
            logger.error("Errore mark_done (upload): %s", e)
            raise
