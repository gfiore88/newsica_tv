import os
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


if __name__ == "__main__":
    unittest.main()
