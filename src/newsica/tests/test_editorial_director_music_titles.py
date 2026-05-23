import os
import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

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

    def test_sanitize_schedule_replaces_thematic_news_titles(self):
        agent = EditorialDirectorAgent()
        schedule = {
            "18:00": {"title": "Focus Ambiente", "type": "news"},
            "19:00": {"title": "Rock & Roll Arena", "type": "music_only", "theme": "rock"},
        }

        sanitized = agent._sanitize_schedule(schedule)

        self.assertEqual(sanitized["18:00"]["title"], "Riepilogo Giornata")
        self.assertNotIn("theme", sanitized["18:00"])
        self.assertEqual(sanitized["19:00"]["title"], "Rock & Roll Arena")

    def test_sanitize_schedule_keeps_general_news_titles(self):
        agent = EditorialDirectorAgent()
        schedule = {
            "20:00": {"title": "Newsica Sera: Il TG Principale", "type": "news"},
        }

        sanitized = agent._sanitize_schedule(schedule)

        self.assertEqual(sanitized["20:00"]["title"], "Newsica Sera: Il TG Principale")

    def test_choose_music_language_forces_italian_from_brief(self):
        agent = EditorialDirectorAgent()
        language = agent.choose_music_language(
            music_mode="full_lyrics",
            custom_brief="vorrei una canzone in italiano romantica",
        )
        self.assertEqual(language, "italian")

    def test_choose_music_language_forces_spanish_for_latin_request(self):
        agent = EditorialDirectorAgent()
        language = agent.choose_music_language(
            music_mode="full_lyrics",
            theme="latin/reggaeton/dembow",
        )
        self.assertIn(language, {"spanish", "italian", "english"})
        with patch("newsica.agents.editorial_director.random.choices", return_value=["spanish"]):
            language = agent.choose_music_language(
                music_mode="full_lyrics",
                theme="latin/reggaeton/dembow",
            )
        self.assertEqual(language, "spanish")

    def test_generate_music_prompt_fallback_carries_target_language(self):
        agent = EditorialDirectorAgent()
        fake_response = Mock(status_code=500)
        with patch.object(agent, "choose_music_mode", return_value="full_lyrics"):
            with patch.object(agent, "_build_localized_music_title", return_value="Luna Dorata"):
                with patch("newsica.agents.editorial_director.requests.post", return_value=fake_response):
                    result = agent.generate_music_prompt(
                        "afternoon",
                        theme="latin/reggaeton/dembow",
                        custom_brief="fammi una hit reggaeton in spagnolo",
                    )

        self.assertEqual(result["language"], "spanish")
        self.assertEqual(result["title"], "Luna Dorata")
        self.assertIn("Lyrics language: Spanish.", result["prompt"])
        self.assertIn("Baila cerca de mí", result["prompt"])
        self.assertNotIn("(Spanish lyrics", result["prompt"])
        self.assertNotIn("Example:", result["prompt"])

    def test_valid_music_prompt_rejects_placeholder_lyrics(self):
        agent = EditorialDirectorAgent()
        prompt = """
Create an HIGH PRODUCTION 180-second Dance Pop song.

Mood: bright.
Tempo: 120 BPM.
Production: clean mix.
Instruments: synths, drums.

Structure:
0:00 - 0:15 intro
0:15 - 0:50 verse/groove
0:50 - 1:10 build/pre-chorus
1:10 - 1:45 chorus/drop/main hook
1:45 - 2:20 second verse or soft bridge
2:20 - 2:52 final chorus/drop/main hook
2:52 - 3:00 final chorus continues with smooth fade out

Vocals:
Modern vocals.

Lyrics:
[Verse 1]
(Italian lyrics about summer and hope)

Ending:
The final 8 seconds must fade out smoothly and naturally. No abrupt ending. No spoken outro.

Negative prompt:
low quality
""".strip()
        self.assertFalse(agent._is_valid_music_prompt(prompt))

    def test_generate_music_prompt_replaces_off_language_title(self):
        agent = EditorialDirectorAgent()
        llm_payload = {
            "title": "Golden Hour",
            "title_language": "english",
            "genre": "dance pop",
            "mood": "uplifting",
            "tempo_bpm": 120,
            "mode": "full_lyrics",
            "lyrics_language": "italian",
            "duration_seconds": 180,
            "fade_out_seconds": 8,
            "prompt": """
Create an HIGH PRODUCTION 180-second Dance Pop song.

Mood: uplifting, warm, radio-friendly.
Tempo: 120 BPM.
Style: modern Italian pop.
Production: clean, polished, streaming-ready.
Instruments: synth bass, bright synths, punchy drums.

Structure:
0:00 - 0:15 intro
0:15 - 0:50 verse/groove
0:50 - 1:10 build/pre-chorus
1:10 - 1:45 chorus/drop/main hook
1:45 - 2:20 second verse or soft bridge
2:20 - 2:52 final chorus/drop/main hook
2:52 - 3:00 final chorus continues with smooth fade out

Vocals:
Male vocals, modern Italian phrasing.

Lyrics:
[Verse 1]
Siamo luce accesa sopra questa città
ogni passo insieme ci riporta qua

[Build]
Sale il ritmo dentro noi
questa notte resta e poi

[Chorus]
Resta qui con me
fino all'alba insieme a me

[Verse 2]
Ogni sogno cambia pelle e verità
ma il tuo sguardo resta la mia libertà

[Chorus]
Resta qui con me
fino all'alba insieme a me

Ending:
The final 8 seconds must fade out smoothly and naturally. No abrupt ending. No spoken outro.

Negative prompt:
low quality, distorted vocals, abrupt ending
""".strip(),
        }
        fake_response = Mock(status_code=200)
        fake_response.json.return_value = {"response": json.dumps(llm_payload)}
        with patch.object(agent, "choose_music_mode", return_value="full_lyrics"):
            with patch.object(agent, "_build_localized_music_title", return_value="Luce Dorata"):
                with patch("newsica.agents.editorial_director.requests.post", return_value=fake_response):
                    result = agent.generate_music_prompt(
                        "afternoon",
                        custom_brief="canzone pop in italiano",
                    )

        self.assertEqual(result["language"], "italian")
        self.assertEqual(result["title"], "Luce Dorata")
        self.assertNotEqual(result["title"], "Golden Hour")


if __name__ == "__main__":
    unittest.main()
