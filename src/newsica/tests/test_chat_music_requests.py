import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

# Aggiunge src al path di importazione
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
sys.modules.setdefault("pytchat", types.SimpleNamespace())
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None))

from chat_agent import extract_music_request
from newsica.audio.chat_music_requests import (
    consume_next_ready_request,
    enqueue_request,
    mark_generating,
    mark_ready,
)


class TestChatMusicRequests(unittest.TestCase):
    def test_extract_music_request_detects_supported_theme(self):
        result = extract_music_request("Vorrei ascoltare un brano rock bello energico")
        self.assertIsNotNone(result)
        self.assertEqual(result["theme"], "rock")

    def test_extract_music_request_returns_none_for_generic_chat(self):
        self.assertIsNone(extract_music_request("Ciao a tutti, bella diretta"))

    def test_queue_lifecycle_ready_to_consumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            requests_file = Path(tmp) / "chat_music_requests.json"

            request = enqueue_request(
                author="@utente",
                message="metti una canzone dance",
                theme="dance/disco",
                custom_brief="dance energica",
                path=requests_file,
            )
            mark_generating(request["id"], path=requests_file)
            mark_ready(
                request["id"],
                audio_path="/tmp/fake_track.wav",
                title="Chat Dance Track",
                path=requests_file,
            )

            consumed = consume_next_ready_request(path=requests_file)

            self.assertIsNotNone(consumed)
            self.assertEqual(consumed["id"], request["id"])
            self.assertEqual(consumed["status"], "queued_for_playout")
            self.assertEqual(consumed["audio_path"], "/tmp/fake_track.wav")


if __name__ == "__main__":
    unittest.main()
