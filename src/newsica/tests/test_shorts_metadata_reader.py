import json
import os
import tempfile
import unittest

from newsica.storage import database
from newsica.storage.repositories.shorts_library_repository import upsert_short, mark_short_social_posts
from newsica.shorts.metadata_reader import (
    normalize_short_hashtags,
    normalize_short_social_posts,
    read_short_metadata,
)


class TestShortsMetadataReader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "newsica_test.db")
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_schema()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_normalize_short_hashtags_limits_to_five_and_deduplicates(self):
        tags = normalize_short_hashtags(["news", "#News", "tech", "", "sport", "wellness", "meteo"])
        self.assertEqual(tags, ["#news", "#tech", "#sport", "#wellness", "#meteo"])

    def test_normalize_short_social_posts_filters_invalid_payloads(self):
        payload = normalize_short_social_posts(
            {
                "youtube": {"posted_at": "2026-05-28T10:00:00", "message": "ok"},
                "instagram": {"posted_at": "", "message": "nope"},
                "tiktok": "invalid",
            }
        )
        self.assertEqual(set(payload.keys()), {"youtube"})

    def test_read_short_metadata_prefers_db_payload(self):
        filename = "short_20260528_101010.mp4"
        upsert_short(
            filename=filename,
            video_path=f"/tmp/{filename}",
            mode="news",
            theme="news",
            news_title="Titolo",
            script="Script",
            caption="Caption",
            hashtags=["#A", "#B"],
        )
        mark_short_social_posts(
            filename,
            {"youtube": {"status": "success", "message": "ok"}},
            posted_at="2026-05-28T10:20:00",
        )
        data = read_short_metadata(f"/tmp/{filename}")
        self.assertEqual(data["news_title"], "Titolo")
        self.assertEqual(data["hashtags_text"], "#A #B")
        self.assertEqual(data["posted_platforms"], ["youtube"])

    def test_read_short_metadata_falls_back_to_json_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, "short_sample.mp4")
            open(video_path, "w", encoding="utf-8").close()
            meta_path = os.path.splitext(video_path)[0] + ".json"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "caption": "Caption sidecar",
                        "hashtags": ["hash1", "hash2"],
                        "news_title": "Sidecar title",
                        "script": "Sidecar script",
                        "theme": "news",
                        "mode": "news",
                    },
                    f,
                    ensure_ascii=False,
                )
            data = read_short_metadata(video_path)
            self.assertEqual(data["news_title"], "Sidecar title")
            self.assertEqual(data["hashtags_text"], "#hash1 #hash2")
            self.assertFalse(data["posted_any"])


if __name__ == "__main__":
    unittest.main()

