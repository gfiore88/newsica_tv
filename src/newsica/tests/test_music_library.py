import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsica.audio.ai_music_generator import write_track_metadata
from newsica.audio.music_library import MusicLibrary
from newsica.audio.music_mode import MUSIC_MODE_AI_ONLY, MUSIC_MODE_MIXED


class TestMusicLibraryModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.music_dir = self.base / "music"
        self.ai_music_dir = self.base / "ai_music"
        self.music_dir.mkdir()
        self.ai_music_dir.mkdir()
        self.library_track = self.music_dir / "library_track.mp3"
        self.ai_track = self.ai_music_dir / "ai_track.wav"
        self.library_track.write_bytes(b"library")
        self.ai_track.write_bytes(b"ai")

    def tearDown(self):
        self.tmp.cleanup()

    def test_ai_only_uses_only_ai_tracks(self):
        library = MusicLibrary(self.music_dir, self.ai_music_dir)

        with patch("newsica.audio.music_library.read_music_mode", return_value=MUSIC_MODE_AI_ONLY):
            selected = {Path(library.get_random_track()).parent.name for _ in range(10)}

        self.assertEqual(selected, {"ai_music"})

    def test_mixed_can_use_both_sources(self):
        library = MusicLibrary(self.music_dir, self.ai_music_dir)

        with patch("newsica.audio.music_library.read_music_mode", return_value=MUSIC_MODE_MIXED):
            selected = {Path(library.get_random_track()).parent.name for _ in range(10)}

        self.assertEqual(selected, {"music", "ai_music"})

    def test_ai_only_without_ai_tracks_returns_none(self):
        self.ai_track.unlink()
        library = MusicLibrary(self.music_dir, self.ai_music_dir)

        with patch("newsica.audio.music_library.read_music_mode", return_value=MUSIC_MODE_AI_ONLY):
            self.assertIsNone(library.get_random_track())

    def test_ai_only_prefers_tracks_with_metadata_sidecar(self):
        extra_ai_track = self.ai_music_dir / "ai_track_2.wav"
        extra_ai_track.write_bytes(b"ai-2")
        extra_ai_track.with_suffix(".json").write_text('{"title": "Cosmic Drift"}\n', encoding="utf-8")
        library = MusicLibrary(self.music_dir, self.ai_music_dir)

        with patch("newsica.audio.music_library.read_music_mode", return_value=MUSIC_MODE_AI_ONLY):
            selected = {Path(library.get_random_track()).name for _ in range(10)}

        self.assertEqual(selected, {"ai_track_2.wav"})

    def test_write_track_metadata_creates_sidecar(self):
        write_track_metadata(
            self.ai_track,
            title="Cosmic Drift",
            prompt="dreamy synthwave",
            duration=180.0,
            mode="instrumental",
            theme="synthwave",
        )

        sidecar = self.ai_track.with_suffix(".json")
        self.assertTrue(sidecar.exists())
        self.assertIn("Cosmic Drift", sidecar.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
