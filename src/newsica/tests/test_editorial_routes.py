import os
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

from newsica.web.editorial_routes import register_editorial_routes


class TestEditorialRoutes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base_dir = self.tmpdir.name
        self.tmp_path = os.path.join(self.tmpdir.name, "tmp")
        self.runtime = os.path.join(self.tmpdir.name, "runtime")
        os.makedirs(self.tmp_path, exist_ok=True)
        os.makedirs(self.runtime, exist_ok=True)

        app = Flask(__name__)
        register_editorial_routes(
            app,
            base_dir=self.base_dir,
            tmp_dir=self.tmp_path,
            control_file=os.path.join(self.runtime, "control.txt"),
            ffmpeg_cmd="ffmpeg",
            python_exec="python3",
            hour_chime_jingle_file=os.path.join(self.tmpdir.name, "missing_jingle.mp3"),
            hour_chime_output_file=os.path.join(self.tmp_path, "hourly_chime.wav"),
            hour_chime_voice_file=os.path.join(self.tmp_path, "hourly_chime_voice.wav"),
        )
        self.client = app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_podcast_requires_topic(self):
        response = self.client.post("/api/podcast", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "ERROR")

    def test_chime_returns_error_if_jingle_missing(self):
        response = self.client.post("/api/chime", json={})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["status"], "ERROR")

    @patch("newsica.web.editorial_routes._generate_manual_event", return_value=({"status": "OK"}, 200))
    def test_manual_event_delegates_to_service(self, mock_generate):
        response = self.client.post(
            "/api/manual-event",
            json={"character_id": "news", "title": "Titolo", "brief": "Brief"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "OK")
        mock_generate.assert_called_once()

    @patch("newsica.web.editorial_routes._build_manual_event_formats", return_value=[{"id": "news"}])
    def test_manual_event_formats_endpoint(self, _mock_formats):
        response = self.client.get("/api/manual-event-formats")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["formats"]), 1)


if __name__ == "__main__":
    unittest.main()
