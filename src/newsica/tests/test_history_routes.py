import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from flask import Flask

from newsica.web.history_routes import register_history_routes


class TestHistoryRoutes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")
        self.runtime_dir = os.path.join(self.tmpdir.name, "runtime")
        os.makedirs(self.runtime_dir, exist_ok=True)

        app = Flask(__name__)
        register_history_routes(app, runtime_dir=self.runtime_dir)
        self.client = app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _build_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS broadcast_history (id INTEGER PRIMARY KEY, block_type TEXT, title TEXT, segment TEXT, asset_path TEXT)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS editorial_memory (id INTEGER PRIMARY KEY, key TEXT, value TEXT)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS asset_slots (id INTEGER PRIMARY KEY, slot_time TEXT, title TEXT)"
        )
        conn.commit()
        conn.close()

    @contextmanager
    def _connection_context(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @patch("newsica.web.history_routes.get_metadata", return_value=None)
    def test_db_history_returns_decorated_rows(self, _mock_meta):
        self._build_db()
        with self._connection_context() as conn:
            conn.execute(
                "INSERT INTO broadcast_history (block_type, title, segment, asset_path) VALUES (?, ?, ?, ?)",
                ("music", "music_rotation", "night", "/tmp/my_song.mp3"),
            )
            conn.commit()

        with patch("newsica.web.history_routes.get_connection", side_effect=self._connection_context):
            response = self.client.get("/api/db/history")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["display_title"], "my song")
        self.assertEqual(payload["data"][0]["display_detail"], "night")

    def test_db_memory_formats_json_values(self):
        self._build_db()
        with self._connection_context() as conn:
            conn.execute(
                "INSERT INTO editorial_memory (key, value) VALUES (?, ?)",
                ("latest_chat", json.dumps({"status": "ok", "message": "ciao"})),
            )
            conn.commit()

        with patch("newsica.web.history_routes.get_connection", side_effect=self._connection_context):
            response = self.client.get("/api/db/memory")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(len(payload["data"]), 1)
        item = payload["data"][0]
        self.assertTrue(item["value_is_json"])
        self.assertIn("status: ok", item["value_summary"])

    @patch("newsica.web.history_routes.get_metadata", return_value=None)
    def test_music_rotation_debug_reads_runtime_files(self, _mock_meta):
        track_path = os.path.join(self.tmpdir.name, "track.wav")
        with open(track_path, "w", encoding="utf-8") as f:
            f.write("x")

        history_file = os.path.join(self.runtime_dir, "music_rotation_history.json")
        blocks_file = os.path.join(self.runtime_dir, "music_rotation_blocks.json")
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump({"recent_tracks": [track_path]}, f)
        with open(blocks_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "events": [
                        {
                            "timestamp": "2026-05-28T08:00:00",
                            "reason": "recent_window",
                            "recent_window": 3,
                            "candidate_count": 10,
                            "blocked_tracks": [track_path],
                        }
                    ]
                },
                f,
            )

        response = self.client.get("/api/db/music-rotation")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["data"]["tracked_count"], 1)
        self.assertEqual(len(payload["data"]["block_events"]), 1)


if __name__ == "__main__":
    unittest.main()
