import unittest
from unittest.mock import MagicMock, patch

from newsica.shorts.plan_executor import process_one_planned_short_item


class TestShortsPlanExecutor(unittest.TestCase):
    @patch("newsica.shorts.plan_executor.get_pending_generation_items", return_value=[])
    def test_process_one_planned_short_item_returns_idle_when_queue_empty(self, mock_pending):
        result = process_one_planned_short_item(due_within_minutes=42)
        self.assertEqual(result.get("status"), "idle")
        mock_pending.assert_called_once_with(limit=1, due_within_minutes=42)

    @patch("newsica.shorts.plan_executor.track_social_posts")
    @patch("newsica.shorts.plan_executor.schedule_short_to_all")
    @patch("newsica.shorts.plan_executor.update_item_status")
    @patch("newsica.agents.content_strategist.ContentStrategistAgent._collect_news")
    @patch("newsica.agents.shorts_agent.ShortsAgent")
    @patch(
        "newsica.shorts.plan_executor.get_pending_generation_items",
        return_value=[
            {
                "id": 17,
                "mode": "breaking",
                "source_title": "Uomo accoltella tre persone in Svizzera gridando Allah Akbar, arrestato",
                "source_summary": "Cronaca estera in aggiornamento.",
                "scheduled_for": {},
            }
        ],
    )
    def test_process_one_planned_short_item_restores_editorial_source_for_breaking(
        self,
        mock_pending,
        mock_agent_cls,
        mock_collect_news,
        mock_update_status,
        mock_schedule,
        mock_track_posts,
    ):
        mock_collect_news.side_effect = [
            [
                {
                    "title": "Uomo accoltella tre persone in Svizzera gridando Allah Akbar, arrestato",
                    "summary": "Cronaca estera in aggiornamento.",
                    "source": "ansa_ultimora",
                    "image_url": "https://example.com/image.jpg",
                }
            ]
        ]
        agent = MagicMock()
        agent.run.return_value = {
            "status": "success",
            "output": "/tmp/breaking.mp4",
            "news_title": "Breaking News",
            "caption": "caption",
            "hashtags": ["#news"],
        }
        mock_agent_cls.return_value = agent
        mock_schedule.return_value = {"status": "success", "message": "ok"}

        result = process_one_planned_short_item()

        self.assertEqual(result.get("status"), "success")
        agent.run.assert_called_once()
        kwargs = agent.run.call_args.kwargs
        self.assertEqual(kwargs["mode"], "breaking")
        self.assertEqual(kwargs["news_item"]["source"], "ansa_ultimora")
        self.assertEqual(kwargs["news_item"]["theme_color"], "breaking")
        self.assertEqual(kwargs["news_item"]["image_url"], "https://example.com/image.jpg")
        mock_pending.assert_called_once_with(limit=1, due_within_minutes=None)
        mock_track_posts.assert_called_once()
        self.assertEqual(mock_update_status.call_args_list[0].args[:2], (17, "generating"))

    @patch("newsica.shorts.plan_executor.track_social_posts")
    @patch("newsica.shorts.plan_executor.schedule_short_to_all")
    @patch("newsica.shorts.plan_executor.update_item_status")
    @patch("newsica.agents.content_strategist.ContentStrategistAgent._collect_news", return_value=[])
    @patch("newsica.agents.shorts_agent.ShortsAgent")
    @patch(
        "newsica.shorts.plan_executor.get_pending_generation_items",
        return_value=[
            {
                "id": 18,
                "mode": "tech",
                "source_title": "Titolo pianificato",
                "source_summary": "Sintesi pianificata.",
                "scheduled_for": {},
            }
        ],
    )
    def test_process_one_planned_short_item_falls_back_when_source_not_found(
        self,
        mock_pending,
        mock_agent_cls,
        mock_collect_news,
        mock_update_status,
        mock_schedule,
        mock_track_posts,
    ):
        agent = MagicMock()
        agent.run.return_value = {
            "status": "success",
            "output": "/tmp/tech.mp4",
            "news_title": "Tech News",
            "caption": "caption",
            "hashtags": ["#tech"],
        }
        mock_agent_cls.return_value = agent
        mock_schedule.return_value = {"status": "success", "message": "ok"}

        result = process_one_planned_short_item()

        self.assertEqual(result.get("status"), "success")
        kwargs = agent.run.call_args.kwargs
        self.assertEqual(kwargs["news_item"]["source"], "tech")
        self.assertEqual(kwargs["news_item"]["summary"], "Sintesi pianificata.")
        self.assertEqual(mock_collect_news.call_count, 2)


if __name__ == "__main__":
    unittest.main()
