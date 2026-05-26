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
        extra_ai_track.with_suffix(".meta").write_text('{"title": "Cosmic Drift"}\n', encoding="utf-8")
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

        sidecar = self.ai_track.with_suffix(".meta")
        self.assertTrue(sidecar.exists())
        self.assertIn("Cosmic Drift", sidecar.read_text(encoding="utf-8"))

    def test_recent_rotation_history_avoids_immediate_repeats_within_window(self):
        extra_library_track = self.music_dir / "library_track_2.mp3"
        extra_ai_track = self.ai_music_dir / "ai_track_2.wav"
        extra_library_track.write_bytes(b"library-2")
        extra_ai_track.write_bytes(b"ai-2")

        history_file = self.base / "runtime" / "music_rotation_history.meta"
        with patch("newsica.audio.music_library.ROTATION_HISTORY_FILE", history_file):
            library = MusicLibrary(self.music_dir, self.ai_music_dir)
            library._recent_tracks.clear()
            library._recent_tracks.extend(
                [
                    str(self.library_track),
                    str(extra_library_track),
                    str(self.ai_track),
                ]
            )

            with patch("newsica.audio.music_library.read_music_mode", return_value=MUSIC_MODE_MIXED):
                with patch("newsica.audio.music_library.random.choice", side_effect=lambda seq: seq[0]):
                    selected = library.get_random_track()

        self.assertEqual(Path(selected).name, "ai_track_2.wav")

    def test_recent_rotation_history_is_loaded_by_new_instance(self):
        history_file = self.base / "runtime" / "music_rotation_history.meta"
        with patch("newsica.audio.music_library.ROTATION_HISTORY_FILE", history_file):
            first = MusicLibrary(self.music_dir, self.ai_music_dir)
            first._remember_track(self.library_track)
            second = MusicLibrary(self.music_dir, self.ai_music_dir)

        self.assertIn(str(self.library_track), list(second._recent_tracks))


if __name__ == "__main__":
    unittest.main()
