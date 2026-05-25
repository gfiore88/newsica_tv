import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsica.audio.music_mode import MUSIC_MODE_AI_ONLY
from newsica.audio.playout import AudioPlayout, _prepare_telegram_voice_for_air


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

    def test_build_post_telegram_restore_metadata_restores_previous_block_and_music(self):
        playout = AudioPlayout(queue.Queue(), None, lambda: False)
        previous_state = {
            "status": "ON_AIR",
            "current_block": "flash_60s",
            "current_title": "Tech in 60 Secondi - Completo",
            "current_segment": "music_rotation_until_deadline",
            "scheduled_slot": "16:00",
            "requested_by": "Giovanni",
            "requested_title": "Messaggio Vocale",
        }

        with patch.object(AudioPlayout, "_probe_music_tags", return_value=("", "")):
            restored = playout.build_post_telegram_restore_metadata(
                previous_state,
                "/tmp/Flashback - Piano Version.mp3",
            )

        self.assertEqual(restored["current_block"], "flash_60s")
        self.assertEqual(restored["current_title"], "Tech in 60 Secondi - Completo")
        self.assertEqual(restored["current_music_title"], "Flashback - Piano Version")
        self.assertEqual(restored["requested_by"], "")
        self.assertEqual(restored["requested_title"], "")

    @patch("newsica.audio.playout.subprocess.run")
    def test_prepare_telegram_voice_for_air_runs_ffmpeg_normalization(self, mock_run):
        self.assertTrue(_prepare_telegram_voice_for_air("/tmp/in.wav", "/tmp/out.wav"))
        args = mock_run.call_args.args[0]
        af_value = args[args.index("-af") + 1]
        self.assertIn("loudnorm=I=-18:TP=-1.5:LRA=7", af_value)
        self.assertIn("acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=3", af_value)


if __name__ == "__main__":
    unittest.main()
