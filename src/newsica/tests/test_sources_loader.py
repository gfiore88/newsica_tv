import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsica.sources import loader


_REGISTRY_TEMPLATE = """RSS_FEED_DEFINITIONS = {
    "ansa_ultimora": {"url": "https://example.com/breaking.xml", "category": "breaking"},
    "ansa_sport": {"url": "https://example.com/sport.xml", "category": "sport"},
}

GENERAL_NEWS_CATEGORIES = {"breaking", "cultura", "economia", "general", "news", "tech"}

RSS_FEEDS = {
    feed_id: entry["url"]
    for feed_id, entry in RSS_FEED_DEFINITIONS.items()
}

NEWS_SOURCES = {
    feed_id
    for feed_id, entry in RSS_FEED_DEFINITIONS.items()
    if entry.get("category", "news") in GENERAL_NEWS_CATEGORIES
}

SPORT_SOURCES = {
    feed_id
    for feed_id, entry in RSS_FEED_DEFINITIONS.items()
    if entry.get("category") == "sport"
}

WELLNESS_SOURCES = set()
MOTORI_SOURCES = set()
NEWS_PREFERRED_SOURCES = ["ansa_ultimora"]
SPORT_PREFERRED_SOURCES = ["ansa_sport"]
WELLNESS_PREFERRED_SOURCES = tuple([])
MOTORI_PREFERRED_SOURCES = []
NEWS_ROTATION_LIMIT = 10
SPORT_ROTATION_LIMIT = 4
MOTORI_ROTATION_LIMIT = 4

def max_items_for_source(source):
    return 12 if source in NEWS_SOURCES else 8
"""


class TestSourcesLoader(unittest.TestCase):
    def test_load_all_sources_detail_reads_registry_python_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.py"
            registry_path.write_text(_REGISTRY_TEMPLATE, encoding="utf-8")

            with patch("newsica.sources.loader._REGISTRY_PATH", registry_path):
                sources = loader.load_all_sources_detail()

        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["id"], "ansa_sport")
        self.assertEqual(sources[1]["category"], "breaking")

    def test_add_source_persists_into_registry_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.py"
            registry_path.write_text(_REGISTRY_TEMPLATE, encoding="utf-8")

            with patch("newsica.sources.loader._REGISTRY_PATH", registry_path):
                loader.add_source("corriere_tech", "https://example.com/tech.xml", "tech")
                feeds = loader.load_rss_feeds()
                registry_content = registry_path.read_text(encoding="utf-8")

        self.assertIn("corriere_tech", feeds)
        self.assertEqual(feeds["corriere_tech"], "https://example.com/tech.xml")
        self.assertIn("corriere_tech", registry_content)

    def test_remove_source_updates_registry_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.py"
            registry_path.write_text(_REGISTRY_TEMPLATE, encoding="utf-8")

            with patch("newsica.sources.loader._REGISTRY_PATH", registry_path):
                removed = loader.remove_source("ansa_sport")
                sources = loader.load_all_sources_detail()

        self.assertTrue(removed)
        self.assertEqual([source["id"] for source in sources], ["ansa_ultimora"])


if __name__ == "__main__":
    unittest.main()
