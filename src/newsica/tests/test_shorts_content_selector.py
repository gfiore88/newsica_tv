import unittest
from unittest.mock import patch

from newsica.shorts.content_selector import ShortContentSelector


class TestShortsContentSelector(unittest.TestCase):
    def test_validate_news_item_rejects_placeholder(self):
        selector = ShortContentSelector()
        ok, message = selector.validate_news_item_for_short(
            {
                "title": "Nessuna notizia disponibile al momento",
                "summary": "Stiamo aggiornando i nostri sistemi.",
                "source": "news",
            },
            "news",
        )
        self.assertFalse(ok)
        self.assertIn("placeholder", message)

    @patch.object(ShortContentSelector, "_load_all_news", return_value=[])
    def test_build_mode_news_item_returns_default_when_empty(self, _mock_news):
        selector = ShortContentSelector()
        item = selector._build_mode_news_item("sport")
        self.assertEqual(item["theme_color"], "sport")
        self.assertIn("Nessuna notizia disponibile", item["title"])


if __name__ == "__main__":
    unittest.main()
