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

    def test_build_music_metadata_uses_library_filename_as_title(self):
        playout = AudioPlayout(queue.Queue(), None, lambda: False)
        with patch.object(AudioPlayout, "_probe_music_tags", return_value=("", "")):
            metadata = playout.build_music_metadata("/tmp/Flashback - Piano Version.mp3")
        self.assertEqual(metadata["current_music_title"], "Flashback - Piano Version")

    def test_build_music_metadata_uses_friendly_ai_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ai_music_dir = base / "ai_music"
            ai_music_dir.mkdir()
            playout = AudioPlayout(queue.Queue(), None, lambda: False)
            playout.music_library.ai_music_dir = ai_music_dir

            metadata = playout.build_music_metadata(str(ai_music_dir / "ai_track_20260522_141032.wav"))

        self.assertEqual(metadata["current_music_title"], "Newsica AI Track")

    def test_build_music_metadata_prefers_artist_and_title_tags(self):
        playout = AudioPlayout(queue.Queue(), None, lambda: False)
        with patch.object(AudioPlayout, "_probe_music_tags", return_value=("Daft Punk", "Voyager")):
            metadata = playout.build_music_metadata("/tmp/unknown.mp3")

        self.assertEqual(metadata["current_music_title"], "Daft Punk - Voyager")

    def test_build_music_metadata_uses_ai_sidecar_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ai_music_dir = base / "ai_music"
            ai_music_dir.mkdir()
            audio_file = ai_music_dir / "ai_track_20260522_141032.wav"
            audio_file.write_bytes(b"ai")
            audio_file.with_suffix(".json").write_text('{"title": "Cosmic Drift"}\n', encoding="utf-8")

            playout = AudioPlayout(queue.Queue(), None, lambda: False)
            playout.music_library.ai_music_dir = ai_music_dir
            metadata = playout.build_music_metadata(str(audio_file))

        self.assertEqual(metadata["current_music_title"], "Cosmic Drift")


if __name__ == "__main__":
    unittest.main()
