import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from newsica.utils.social_publisher import SocialPublisher


class TestSocialPublisher(unittest.TestCase):
    @patch.dict("os.environ", {"BUFFER_USE_INTEGRATION": "true"}, clear=False)
    def test_publish_to_all_socials_reuses_single_cloudinary_upload_with_buffer(self):
        publisher = SocialPublisher()

        with patch.object(publisher, "_upload_to_cloudinary", return_value="https://cdn.example/video.mp4") as mock_upload, patch.object(
            publisher,
            "_publish_via_buffer",
            side_effect=[
                {"status": "success", "message": "YT ok"},
                {"status": "success", "message": "IG ok"},
                {"status": "success", "message": "TT ok"},
            ],
        ) as mock_publish:
            result = publisher.publish_to_all_socials("/tmp/short.mp4", "Titolo Test", "Caption Test")

        self.assertEqual(result["status"], "success")
        self.assertEqual(mock_upload.call_count, 1)
        self.assertEqual(mock_publish.call_count, 3)
        self.assertEqual(result["results"]["instagram"]["message"], "IG ok")

    @patch.dict("os.environ", {"BUFFER_USE_INTEGRATION": "false"}, clear=False)
    def test_publish_to_all_socials_reports_partial_when_one_platform_fails(self):
        publisher = SocialPublisher()

        with patch.object(publisher, "publish_to_youtube", return_value={"status": "success", "message": "YT ok"}), patch.object(
            publisher,
            "publish_to_instagram",
            return_value={"status": "config_missing", "message": "IG missing"},
        ), patch.object(
            publisher,
            "publish_to_tiktok",
            return_value={"status": "error", "message": "TT fail"},
        ):
            result = publisher.publish_to_all_socials("/tmp/short.mp4", "Titolo Test", "Caption Test")

        self.assertEqual(result["status"], "partial")
        self.assertIn("[OK] YouTube: YT ok", result["message"])
        self.assertIn("[KO] Instagram: IG missing", result["message"])
        self.assertIn("[KO] TikTok: TT fail", result["message"])

    @patch.dict("os.environ", {"BUFFER_USE_INTEGRATION": "true"}, clear=False)
    def test_schedule_to_all_socials_uses_scheduled_mode(self):
        publisher = SocialPublisher()
        due_map = {
            "youtube": {"utc": "2026-05-28T10:00:00Z"},
            "instagram": {"utc": "2026-05-28T11:00:00Z"},
            "tiktok": {"utc": "2026-05-28T12:00:00Z"},
        }
        with patch.object(publisher, "_upload_to_cloudinary", return_value="https://cdn.example/video.mp4"), patch.object(
            publisher,
            "_publish_via_buffer",
            return_value={"status": "success", "message": "ok"},
        ) as mock_publish:
            result = publisher.schedule_to_all_socials("/tmp/short.mp4", "Titolo", "Caption", due_map)

        self.assertEqual(result["status"], "success")
        self.assertEqual(mock_publish.call_count, 3)
        for call in mock_publish.call_args_list:
            self.assertEqual(call.kwargs.get("publish_mode"), "scheduled")
            self.assertTrue(call.kwargs.get("due_at_utc"))

    def test_normalize_due_at_utc_pushes_past_timestamp_forward(self):
        publisher = SocialPublisher()
        normalized = publisher._normalize_due_at_utc("2020-01-01T10:00:00Z")
        normalized_dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        self.assertGreaterEqual(normalized_dt, datetime.now(timezone.utc) + timedelta(minutes=4))


if __name__ == "__main__":
    unittest.main()
