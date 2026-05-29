import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from newsica.generation.client import (
    GenerationDeferred,
    GenerationModeError,
    LocalGenerationClient,
    RemoteGenerationClient,
    get_generation_client,
    get_generation_mode,
)


class TestGenerationClient(unittest.TestCase):
    def test_generation_mode_defaults_to_local(self):
        self.assertEqual(get_generation_mode({}), "local")

    def test_generation_mode_rejects_unknown_value(self):
        with self.assertRaises(GenerationModeError):
            get_generation_mode({"NEWSICA_GENERATION_MODE": "hybrid"})

    def test_factory_returns_local_client_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(get_generation_client(), LocalGenerationClient)

    @patch("newsica.agents.ai_integrator.AIIntegratorAgent")
    def test_local_client_reuses_ai_integrator_pipeline(self, mock_integrator_cls):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "audio.wav"
            integrator = MagicMock()
            integrator.generate_script.return_value = "script"
            integrator.generate_audio.return_value = [audio_path]
            mock_integrator_cls.return_value = integrator

            result = LocalGenerationClient().generate_slot_audio(
                {"character_id": "news"},
                tmp,
            )

        mock_integrator_cls.assert_called_once()
        integrator.generate_script.assert_called_once_with({"character_id": "news"})
        integrator.generate_audio.assert_called_once_with("script", {"character_id": "news"})
        self.assertEqual(result.script_text, "--- SHOW PRINCIPALE ---\nscript")
        self.assertEqual(result.audio_files, [audio_path])

    @patch("newsica.audio.ai_music_runtime.schedule_rotation_fill_job")
    def test_local_client_reuses_ai_music_scheduler(self, mock_schedule):
        mock_schedule.return_value = ({"id": "job1"}, True)

        job, created = LocalGenerationClient().schedule_ai_music("test", theme="rock")

        self.assertEqual(job["id"], "job1")
        self.assertTrue(created)
        mock_schedule.assert_called_once_with("test", theme="rock")

    def test_remote_client_requires_env_configuration(self):
        with patch.dict(
            os.environ,
            {"NEWSICA_GENERATION_MODE": "remote", "NEWSICA_REMOTE_GENERATION_QUEUE": "http"},
            clear=True,
        ):
            with self.assertRaisesRegex(GenerationModeError, "NEWSICA_REMOTE_GENERATION_URL"):
                get_generation_client()

    @patch("newsica.storage.repositories.generation_jobs_repository.enqueue_job")
    def test_remote_client_enqueues_slot_audio_and_defers(self, mock_enqueue):
        mock_enqueue.return_value = ({"id": "job1"}, True)

        with self.assertRaises(GenerationDeferred) as ctx:
            RemoteGenerationClient().generate_slot_audio(
                {"slot_time": "10:00", "character_id": "news", "title": "Morning News"},
                "/tmp/work",
            )

        self.assertEqual(ctx.exception.job["id"], "job1")
        mock_enqueue.assert_called_once()
        self.assertEqual(mock_enqueue.call_args.args[0], "slot_audio")

    @patch("newsica.storage.repositories.generation_jobs_repository.enqueue_job")
    def test_remote_client_enqueues_ai_music(self, mock_enqueue):
        mock_enqueue.return_value = ({"id": "music1"}, True)

        job, created = RemoteGenerationClient().schedule_ai_music("test", theme="Rock Arena")

        self.assertTrue(created)
        self.assertEqual(job["id"], "music1")
        kwargs = mock_enqueue.call_args.kwargs
        self.assertEqual(kwargs["theme"], "rock arena")
        self.assertEqual(kwargs["dedupe_key"], "ai_music:rotation_fill:rock arena")


if __name__ == "__main__":
    unittest.main()
