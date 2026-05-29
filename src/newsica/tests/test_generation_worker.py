import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from newsica.generation.worker import process_job
from newsica.storage import database
from newsica.storage.repositories import generation_jobs_repository as repo


class TestGenerationWorker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "newsica_test.db")
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_schema()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    @patch("newsica.generation.worker.AIIntegratorAgent")
    def test_process_slot_audio_marks_job_ready_with_manifest(self, mock_integrator_cls):
        work_dir = Path(self.temp_dir.name) / "work"
        audio_path = work_dir / "audio.wav"
        integrator = MagicMock()
        integrator.generate_script.return_value = "script"
        integrator.generate_audio.return_value = [audio_path]
        mock_integrator_cls.return_value = integrator
        job, _ = repo.enqueue_job(
            "slot_audio",
            payload={
                "target_work_dir": str(work_dir),
                "content_data": {
                    "character_id": "news",
                    "title": "Morning News",
                    "slot_time": "10:00",
                },
            },
        )
        claimed = repo.claim_next_job("worker-a")

        ready = process_job(claimed, "worker-a")

        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["artifact_manifest"]["kind"], "slot_audio")
        self.assertEqual(ready["artifact_manifest"]["title"], "Morning News")

    @patch("newsica.generation.worker.generate_track")
    def test_process_ai_music_marks_job_ready_with_manifest(self, mock_generate):
        mock_generate.return_value = (Path("/tmp/song.wav"), "Song Title")
        job, _ = repo.enqueue_job("ai_music", theme="rock", payload={"theme": "rock"})
        claimed = repo.claim_next_job("worker-a")

        ready = process_job(claimed, "worker-a")

        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["artifact_manifest"]["kind"], "ai_music")
        self.assertEqual(ready["artifact_manifest"]["title"], "Song Title")


if __name__ == "__main__":
    unittest.main()
