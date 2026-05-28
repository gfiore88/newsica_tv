import os
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

from newsica.web.control_routes import register_control_routes


class TestControlRoutes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.runtime_dir = os.path.join(self.tmpdir.name, "runtime")
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.control_file = os.path.join(self.runtime_dir, "control.txt")

        app = Flask(__name__)
        register_control_routes(app, control_file=self.control_file, runtime_dir=self.runtime_dir)
        self.client = app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch("newsica.web.control_routes.get_current_schedule", return_value={"12:00": {"title": "Noon", "type": "news"}})
    @patch("newsica.broadcast.runtime_state.get_current_state", return_value={"status": "OK"})
    def test_state_endpoint_returns_schedule(self, _mock_state, _mock_schedule):
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(len(payload["schedule"]), 1)
        self.assertEqual(payload["schedule"][0]["time"], "12:00")

    def test_command_endpoint_writes_control_file(self):
        response = self.client.post("/api/command", json={"command": "PING"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "OK")
        with open(self.control_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "PING")

    def test_music_mode_rejects_invalid_value(self):
        response = self.client.post("/api/music_mode", json={"mode": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "ERROR")

    @patch("newsica.web.control_routes.read_music_mode", return_value="mixed")
    @patch("newsica.web.control_routes.MusicLibrary.get_counts", return_value={"ai": 1, "music": 3, "total": 4})
    def test_music_mode_get_returns_payload(self, _mock_counts, _mock_mode):
        response = self.client.get("/api/music_mode")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["mode"], "mixed")
        self.assertIn("counts", payload)

    def test_audit_log_empty_returns_default_message(self):
        response = self.client.get("/api/audit-log")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["lines"]), 1)
        self.assertIn("Audit Log", payload["lines"][0])


if __name__ == "__main__":
    unittest.main()
