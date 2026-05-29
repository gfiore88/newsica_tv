import os
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

from newsica.web.system_routes import register_system_routes


class TestSystemRoutes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = self.tmpdir.name
        self.tmp_path = os.path.join(self.tmpdir.name, "tmp")
        os.makedirs(self.tmp_path, exist_ok=True)
        self.ace_step_python = os.path.join(self.tmpdir.name, "missing_ace_step_python")
        self.services = {
            "director": {"label": "Regia", "patterns": [], "command": ["true"], "log": os.path.join(self.tmp_path, "director.log")},
            "stream": {"label": "Stream", "patterns": [], "command": ["true"], "log": os.path.join(self.tmp_path, "stream.log")},
            "ai_music_worker": {"label": "Musica AI Worker", "patterns": [], "command": ["true"], "log": os.path.join(self.tmp_path, "worker.log")},
            "telegram_agent": {"label": "Telegram Bot", "patterns": [], "command": ["true"], "log": os.path.join(self.tmp_path, "telegram.log")},
            "chat_agent": {"label": "YouTube Chat", "patterns": [], "command": ["true"], "log": os.path.join(self.tmp_path, "chat.log")},
        }

        app = Flask(__name__)
        register_system_routes(
            app,
            base_dir=self.base_dir,
            tmp_dir=self.tmp_path,
            services=self.services,
            ace_step_python=self.ace_step_python,
        )
        self.client = app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_chat_video_id_rejects_invalid_length(self):
        response = self.client.post("/api/chat/video_id", json={"video_id": "short"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "INVALID")

    def test_chat_video_id_persists_valid_id(self):
        response = self.client.post("/api/chat/video_id", json={"video_id": "ABCDEFGHIJK"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "OK")
        with open(os.path.join(self.tmp_path, "live_video_id.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "ABCDEFGHIJK")

    @patch("newsica.web.system_routes._find_pids", return_value=[])
    def test_chat_status_reads_video_id_and_running_flag(self, _mock_find):
        with open(os.path.join(self.tmp_path, "live_video_id.txt"), "w", encoding="utf-8") as f:
            f.write("12345678901")
        response = self.client.get("/api/chat/status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["video_id"], "12345678901")
        self.assertFalse(payload["is_running"])

    def test_service_restart_rejects_unknown_service(self):
        response = self.client.post("/api/service/restart", json={"service": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "INVALID")

    def test_music_gen_requires_ace_step_env(self):
        response = self.client.post("/api/music_gen", json={})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["status"], "ERROR")

    @patch("newsica.web.system_routes.list_generation_jobs")
    def test_generation_jobs_route_lists_jobs(self, mock_list_jobs):
        mock_list_jobs.return_value = [{"id": "job1", "status": "pending"}]

        response = self.client.get("/api/generation/jobs?status=pending&limit=10")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["jobs"][0]["id"], "job1")
        mock_list_jobs.assert_called_once_with(status="pending", limit=10)

    @patch("newsica.web.system_routes.generation_jobs_repository.get_summary")
    def test_generation_summary_route_returns_counts(self, mock_summary):
        mock_summary.return_value = {"counts": {"pending": 2}, "active_workers": [], "latest_jobs": []}

        response = self.client.get("/api/generation/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["summary"]["counts"]["pending"], 2)
        self.assertGreater(payload["max_upload_mb"], 0)

    def test_generation_claim_requires_token_configuration(self):
        response = self.client.post("/api/generation/jobs/claim", json={"worker_id": "worker-a"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "ERROR")

    @patch("newsica.web.system_routes.generation_jobs_repository.claim_next_job")
    @patch.dict(os.environ, {"NEWSICA_REMOTE_GENERATION_TOKEN": "test-token"}, clear=False)
    def test_generation_claim_uses_bearer_token(self, mock_claim):
        mock_claim.return_value = {"id": "job1", "status": "claimed"}

        response = self.client.post(
            "/api/generation/jobs/claim",
            json={"worker_id": "worker-a", "job_types": ["slot_audio"]},
            headers={"Authorization": "Bearer test-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["job"]["id"], "job1")
        mock_claim.assert_called_once_with("worker-a", job_types=["slot_audio"])

    @patch("newsica.web.system_routes.generation_jobs_repository.heartbeat")
    @patch.dict(os.environ, {"NEWSICA_REMOTE_GENERATION_TOKEN": "test-token"}, clear=False)
    def test_generation_heartbeat_requires_worker_id(self, mock_heartbeat):
        response = self.client.post(
            "/api/generation/jobs/job1/heartbeat",
            json={},
            headers={"X-Newsica-Generation-Token": "test-token"},
        )

        self.assertEqual(response.status_code, 400)
        mock_heartbeat.assert_not_called()

    @patch("newsica.web.system_routes.generation_jobs_repository.get_job")
    @patch.dict(os.environ, {"NEWSICA_REMOTE_GENERATION_TOKEN": "test-token"}, clear=False)
    def test_generation_artifact_upload_publishes_slot_audio(self, mock_get_job):
        mock_get_job.return_value = {
            "id": "job1",
            "job_type": "slot_audio",
            "worker_id": "worker-a",
            "slot_time": "10:00",
            "character": "news",
            "title": "Morning News",
        }
        with tempfile.TemporaryDirectory() as assets_tmp, patch.dict(
            os.environ,
            {"NEWSICA_RUNTIME_ASSETS_DIR": assets_tmp},
            clear=False,
        ):
            manifest = {
                "kind": "slot_audio",
                "slot_time": "10:00",
                "character": "news",
                "title": "Morning News",
                "audio_files": ["audio.wav"],
            }
            response = self.client.post(
                "/api/generation/jobs/job1/artifact",
                data={
                    "worker_id": "worker-a",
                    "manifest_json": json.dumps(manifest),
                    "files": (io.BytesIO(b"audio"), "audio.wav"),
                },
                headers={"Authorization": "Bearer test-token"},
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["status"], "OK")
            self.assertTrue(os.path.exists(os.path.join(assets_tmp, "ready", "1000", "audio.wav")))

    @patch("newsica.web.system_routes.cleanup_incoming_artifacts", return_value=3)
    @patch.dict(os.environ, {"NEWSICA_REMOTE_GENERATION_TOKEN": "test-token"}, clear=False)
    def test_generation_incoming_cleanup_requires_token_and_runs(self, mock_cleanup):
        response = self.client.post(
            "/api/generation/incoming/cleanup",
            json={"older_than_seconds": 10},
            headers={"Authorization": "Bearer test-token"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["removed"], 3)
        mock_cleanup.assert_called_once_with(older_than_seconds=10)


if __name__ == "__main__":
    unittest.main()
