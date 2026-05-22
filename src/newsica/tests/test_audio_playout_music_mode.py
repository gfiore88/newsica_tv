import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsica.audio.music_mode import MUSIC_MODE_AI_ONLY
from newsica.audio.playout import AudioPlayout


class TestAudioPlayoutMusicMode(unittest.TestCase):
    def test_ai_only_replaces_explicit_library_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            music_dir = base / "music"
            ai_music_dir = base / "ai_music"
            music_dir.mkdir()
            ai_music_dir.mkdir()
            library_track = music_dir / "normal.mp3"
            ai_track = ai_music_dir / "ai.wav"
            library_track.write_bytes(b"normal")
            ai_track.write_bytes(b"ai")

            playout = AudioPlayout(queue.Queue(), None, lambda: False)
            playout.music_library.music_dir = music_dir
            playout.music_library.ai_music_dir = ai_music_dir

            with patch("newsica.audio.playout.read_music_mode", return_value=MUSIC_MODE_AI_ONLY):
                selected = playout._ensure_music_allowed_by_mode(str(library_track))

            self.assertEqual(Path(selected).parent, ai_music_dir)


if __name__ == "__main__":
    unittest.main()
