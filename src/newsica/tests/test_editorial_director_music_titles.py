import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsica.agents.editorial_director import EditorialDirectorAgent
from newsica.editorial import memory


class TestEditorialDirectorMusicTitles(unittest.TestCase):
    def test_rejects_recent_dominant_word_reuse(self):
        agent = EditorialDirectorAgent()
        self.assertTrue(
            agent._is_music_title_too_similar(
                "Electric Pulse",
                ["Neon Pulse", "Solar Drift"],
            )
        )

    def test_allows_distinct_title(self):
        agent = EditorialDirectorAgent()
        self.assertFalse(
            agent._is_music_title_too_similar(
                "Golden Mirage",
                ["Neon Pulse", "Electric Beat"],
            )
        )

    def test_recent_music_titles_are_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_file = Path(tmp) / "editorial-memory.json"
            with patch.object(memory, "MEMORY_FILE", str(memory_file)):
                memory.add_music_title("Neon Pulse")
                memory.add_music_title("Golden Mirage")

                recent = memory.get_recent_music_titles(limit=8)

        self.assertEqual(recent, ["Neon Pulse", "Golden Mirage"])


if __name__ == "__main__":
    unittest.main()
