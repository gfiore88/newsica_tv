import unittest

from newsica.shorts.caption_builder import generate_social_copy


class TestShortsCaptionBuilder(unittest.TestCase):
    def test_generate_social_copy_includes_title_and_followup(self):
        caption, hashtags = generate_social_copy(
            {"title": "Nuovo aggiornamento meteo", "theme_color": "meteo"},
            "Pioggia intensa in arrivo su Milano #meteo",
        )
        self.assertIn("Nuovo aggiornamento meteo", caption)
        self.assertIn("Seguici per altri aggiornamenti", caption)
        self.assertTrue(hashtags)
        self.assertLessEqual(len(hashtags), 5)

    def test_generate_social_copy_deduplicates_hashtags(self):
        caption, hashtags = generate_social_copy(
            {"title": "Tech AI", "theme_color": "tech"},
            "AI AI AI innovazione innovazione #AI #AI",
        )
        self.assertTrue(caption)
        self.assertEqual(len(hashtags), len({tag.lower() for tag in hashtags}))


if __name__ == "__main__":
    unittest.main()
