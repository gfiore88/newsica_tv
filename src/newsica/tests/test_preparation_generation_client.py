import unittest
from unittest.mock import MagicMock, patch

import preparation_agent


class TestPreparationGenerationClient(unittest.TestCase):
    @patch("preparation_agent.count_active_jobs", return_value=0)
    @patch("preparation_agent.MusicLibrary")
    def test_ensure_theme_music_ready_uses_generation_client(self, mock_library_cls, mock_count):
        library = MagicMock()
        library.count_ai_tracks_for_theme.return_value = 0
        mock_library_cls.return_value = library
        generation_client = MagicMock()
        generation_client.schedule_ai_music.return_value = ({"id": "job1"}, True)

        preparation_agent.ensure_theme_music_ready("  Rock   Arena  ", generation_client=generation_client)

        generation_client.schedule_ai_music.assert_called()
        args, kwargs = generation_client.schedule_ai_music.call_args
        self.assertEqual(args[0], "preparation_agent")
        self.assertEqual(kwargs["theme"], "rock arena")


if __name__ == "__main__":
    unittest.main()
