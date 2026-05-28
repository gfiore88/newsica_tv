import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from newsica.audio import music_metadata


class TestAudioMusicMetadata(unittest.TestCase):
    def setUp(self):
        music_metadata.probe_music_tags.cache_clear()

    @patch("newsica.audio.music_metadata.subprocess.run")
    def test_probe_music_tags_parses_artist_and_title(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format":{"tags":{"artist":"  Daft  Punk  ","title":"  Voyager  "}}}',
        )
        artist, title = music_metadata.probe_music_tags("/tmp/test.mp3")
        self.assertEqual(artist, "Daft Punk")
        self.assertEqual(title, "Voyager")

    def test_read_music_tags_skips_ai_directory(self):
        ai_dir = Path("/tmp/ai_music")
        track = ai_dir / "ai_track.wav"
        probe = MagicMock(return_value=("A", "B"))
        artist, title = music_metadata.read_music_tags(track, ai_dir, probe_tags=probe)
        self.assertEqual((artist, title), ("", ""))
        self.assertFalse(probe.called)

    def test_display_title_for_music_file_uses_ai_friendly_fallback(self):
        ai_dir = Path("/tmp/ai_music")
        title = music_metadata.display_title_for_music_file(
            str(ai_dir / "ai_track_1.wav"),
            ai_dir,
            read_ai_sidecar_title_fn=lambda _: "",
            read_music_tags_fn=lambda _: ("", ""),
        )
        self.assertEqual(title, "Newsica AI Track")

    def test_build_post_telegram_restore_metadata_resets_requested_fields(self):
        previous = {"current_block": "flash_60s", "requested_by": "Mario", "requested_title": "Song"}
        restored = music_metadata.build_post_telegram_restore_metadata(
            previous,
            "/tmp/music.mp3",
            metadata_builder=lambda music_file, state: {**state, "current_music_title": "Track"},
        )
        self.assertEqual(restored["current_block"], "flash_60s")
        self.assertEqual(restored["current_music_title"], "Track")
        self.assertEqual(restored["requested_by"], "")
        self.assertEqual(restored["requested_title"], "")


if __name__ == "__main__":
    unittest.main()
