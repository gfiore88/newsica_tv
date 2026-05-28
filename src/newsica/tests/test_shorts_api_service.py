import os
import tempfile
import unittest
from unittest.mock import patch

from newsica.shorts.api_service import (
    delete_shorts_payload,
    normalize_short_mode,
)


class TestShortsApiService(unittest.TestCase):
    def test_normalize_short_mode_rejects_invalid_mode(self):
        self.assertIsNone(normalize_short_mode("invalid-mode"))

    def test_normalize_short_mode_keeps_valid_mode(self):
        self.assertEqual(normalize_short_mode("NeWs"), "news")

    @patch("newsica.shorts.api_service.delete_shorts", return_value=1)
    def test_delete_shorts_payload_removes_video_and_sidecar(self, _mock_delete):
        with tempfile.TemporaryDirectory() as tmp:
            shorts_dir = os.path.join(tmp, "output", "shorts")
            os.makedirs(shorts_dir, exist_ok=True)
            video = os.path.join(shorts_dir, "short_test.mp4")
            sidecar = os.path.join(shorts_dir, "short_test.json")
            open(video, "w", encoding="utf-8").close()
            open(sidecar, "w", encoding="utf-8").close()

            payload, code = delete_shorts_payload(tmp, ["short_test.mp4"])
            self.assertEqual(code, 200)
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["deleted_files"], 1)
            self.assertFalse(os.path.exists(video))
            self.assertFalse(os.path.exists(sidecar))

    def test_delete_shorts_payload_rejects_empty_selection(self):
        payload, code = delete_shorts_payload("/tmp", [])
        self.assertEqual(code, 400)
        self.assertEqual(payload["status"], "error")


if __name__ == "__main__":
    unittest.main()

