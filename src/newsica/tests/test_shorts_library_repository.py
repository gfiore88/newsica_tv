import json
import os
import tempfile
import unittest

from newsica.storage import database
from newsica.storage.repositories.shorts_library_repository import (
    get_short,
    mark_short_social_posts,
    upsert_short,
)


class TestShortsLibraryRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "newsica_test.db")
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_schema()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_mark_short_social_posts_persists_successful_platforms(self):
        upsert_short(
            filename="short_20260101_101010.mp4",
            video_path="/tmp/short.mp4",
            mode="news",
            theme="news",
            news_title="Test",
            caption="Caption",
            hashtags=["#NewsicaTV"],
        )

        social_posts = mark_short_social_posts(
            "short_20260101_101010.mp4",
            {
                "youtube": {"status": "success", "message": "YT ok"},
                "instagram": {"status": "error", "message": "IG fail"},
                "tiktok": {"status": "success", "message": "TT ok"},
            },
            posted_at="2026-01-01T10:20:30",
        )

        self.assertEqual(set(social_posts.keys()), {"youtube", "tiktok"})
        saved = get_short("short_20260101_101010.mp4")
        saved_posts = json.loads(saved["social_posts_json"])
        self.assertEqual(saved_posts["youtube"]["posted_at"], "2026-01-01T10:20:30")
        self.assertEqual(saved_posts["tiktok"]["message"], "TT ok")
        self.assertNotIn("instagram", saved_posts)


if __name__ == "__main__":
    unittest.main()
