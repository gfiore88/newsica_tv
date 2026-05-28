import unittest
from unittest.mock import patch

from newsica.shorts.social_service import (
    build_full_caption,
    publish_short,
    schedule_short_to_all,
    track_social_posts,
)


class TestShortsSocialService(unittest.TestCase):
    def test_build_full_caption_with_list_hashtags(self):
        result = build_full_caption("Testo", ["#one", " #two "])
        self.assertEqual(result, "Testo\n\n#one #two")

    def test_build_full_caption_with_text_hashtags(self):
        result = build_full_caption("Testo", "#one #two")
        self.assertEqual(result, "Testo\n\n#one #two")

    def test_publish_short_raises_on_unsupported_platform(self):
        with self.assertRaises(ValueError):
            publish_short("/tmp/short.mp4", "Titolo", "Caption", "unsupported")

    @patch("newsica.shorts.social_service.SocialPublisher")
    def test_schedule_short_to_all_delegates_to_publisher(self, mock_publisher_cls):
        mock_publisher = mock_publisher_cls.return_value
        mock_publisher.schedule_to_all_socials.return_value = {"status": "success"}
        due_map = {"youtube": {"utc": "2026-05-28T12:00:00Z"}}
        result = schedule_short_to_all("/tmp/short.mp4", "Titolo", "Caption", due_map)
        self.assertEqual(result["status"], "success")
        mock_publisher.schedule_to_all_socials.assert_called_once()

    @patch("newsica.shorts.social_service.mark_short_social_posts", return_value={"youtube": {"posted_at": "x"}})
    def test_track_social_posts_wraps_single_platform_result(self, mock_track):
        result = track_social_posts(
            "short_test.mp4",
            "youtube",
            {"status": "success", "message": "ok"},
        )
        self.assertEqual(result, {"youtube": {"posted_at": "x"}})
        mock_track.assert_called_once_with(
            "short_test.mp4",
            {"youtube": {"status": "success", "message": "ok"}},
        )


if __name__ == "__main__":
    unittest.main()
