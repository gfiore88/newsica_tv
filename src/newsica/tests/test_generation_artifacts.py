import json
import tempfile
import unittest
from pathlib import Path

from newsica.generation.artifacts import (
    ArtifactValidationError,
    cleanup_incoming_artifacts,
    publish_ai_music_artifact,
    publish_slot_audio_artifact,
    validate_ai_music_artifact,
    validate_slot_audio_artifact,
)


class TestGenerationArtifacts(unittest.TestCase):
    def test_validate_slot_audio_artifact_accepts_matching_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "audio.wav").write_bytes(b"audio")
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "slot_time": "10:00",
                        "character": "news",
                        "title": "Morning News",
                        "audio_files": ["audio.wav"],
                    }
                ),
                encoding="utf-8",
            )

            manifest = validate_slot_audio_artifact(
                root,
                {"slot_time": "10:00", "character": "news", "title": "Morning News"},
            )

        self.assertEqual(manifest["title"], "Morning News")

    def test_validate_slot_audio_artifact_rejects_title_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "audio.wav").write_bytes(b"audio")
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "slot_time": "10:00",
                        "character": "news",
                        "title": "Different",
                        "audio_files": ["audio.wav"],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ArtifactValidationError):
                validate_slot_audio_artifact(
                    root,
                    {"slot_time": "10:00", "character": "news", "title": "Morning News"},
                )

    def test_publish_slot_audio_artifact_moves_copy_to_ready_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            incoming = base / "incoming" / "job1"
            incoming.mkdir(parents=True)
            (incoming / "audio.wav").write_bytes(b"audio")
            (incoming / "manifest.json").write_text("{}", encoding="utf-8")

            ready_dir = publish_slot_audio_artifact(incoming, "10:00", assets_dir=base / "assets")

            self.assertEqual(ready_dir.name, "1000")
            self.assertTrue((ready_dir / "audio.wav").exists())

    def test_publish_ai_music_artifact_copies_audio_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            incoming = base / "incoming" / "job1"
            incoming.mkdir(parents=True)
            (incoming / "song.wav").write_bytes(b"audio")
            (incoming / "manifest.json").write_text(
                json.dumps({"kind": "ai_music", "audio_file": "song.wav", "title": "Song"}),
                encoding="utf-8",
            )

            manifest = validate_ai_music_artifact(incoming)
            target = publish_ai_music_artifact(incoming, assets_dir=base / "assets")

            self.assertEqual(manifest["audio_file"], "song.wav")
            self.assertTrue(target.exists())
            self.assertTrue(target.with_suffix(target.suffix + ".json").exists())

    def test_cleanup_incoming_artifacts_removes_old_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            old_dir = base / "incoming" / "old-job"
            new_dir = base / "incoming" / "new-job"
            old_dir.mkdir(parents=True)
            new_dir.mkdir(parents=True)
            old_time = 1000
            old_dir.touch()
            import os
            os.utime(old_dir, (old_time, old_time))

            removed = cleanup_incoming_artifacts(older_than_seconds=1, assets_dir=base)

            self.assertEqual(removed, 1)
            self.assertFalse(old_dir.exists())
            self.assertTrue(new_dir.exists())


if __name__ == "__main__":
    unittest.main()
