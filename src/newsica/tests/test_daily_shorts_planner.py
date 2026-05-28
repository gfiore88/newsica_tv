import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from newsica.shorts.daily_planner import DailyShortsPlanner


class TestDailyShortsPlanner(unittest.TestCase):
    def test_build_items_enforces_always_constraints_and_conditional_relevance(self):
        planner = DailyShortsPlanner()
        fake_news = [
            {"title": "Governo approva nuova manovra", "summary": "Economia e politica", "source": "ansa_politica"},
            {"title": "Nuovo modello AI rivoluziona i chip", "summary": "Innovazione nel settore", "source": "ansa_tecnologia"},
            {"title": "Alluvione con allerta rossa in Liguria", "summary": "Situazione meteo critica", "source": "meteo"},
            {"title": "Finale europea decisa ai rigori", "summary": "Vittoria storica", "source": "ansa_sport"},
            {"title": "Routine benessere per migliorare il sonno", "summary": "Salute e abitudini", "source": "ansa_salute_benessere"},
            {"title": "Trend social curioso del giorno", "summary": "Fenomeno virale", "source": "ansa_lifestyle"},
        ]

        items = planner._build_items(fake_news, target_day=date(2026, 5, 27))

        modes = [item["mode"] for item in items]
        self.assertIn("news", modes)
        self.assertIn("funfact", modes)
        self.assertIn("tech", modes)
        self.assertIn("meteo", modes)
        self.assertGreaterEqual(len(modes), 4)

    def test_compute_platform_schedule_emits_utc_for_each_platform(self):
        planner = DailyShortsPlanner()
        data = planner._compute_platform_schedule(date(2026, 5, 27), 0)
        self.assertIn("instagram", data)
        self.assertIn("tiktok", data)
        self.assertIn("youtube", data)
        self.assertTrue(data["instagram"]["utc"].endswith("Z"))

    def test_compute_platform_schedule_keeps_due_times_in_future(self):
        planner = DailyShortsPlanner()
        tz = ZoneInfo(planner.timezone)
        now_local = datetime(2026, 5, 27, 23, 50, tzinfo=tz)
        data = planner._compute_platform_schedule(date(2026, 5, 27), 0, now_local=now_local)

        for platform in ("instagram", "tiktok", "youtube"):
            due_local = datetime.fromisoformat(data[platform]["local"])
            self.assertGreaterEqual(due_local, now_local + timedelta(minutes=1))

    @patch.dict("os.environ", {"SHORTS_DAILY_DAWN_TIME": "05:30"}, clear=False)
    def test_should_run_automatic_reconcile_only_after_dawn(self):
        planner = DailyShortsPlanner()
        tz = ZoneInfo(planner.timezone)
        before_dawn = datetime(2026, 5, 27, 5, 29, tzinfo=tz)
        after_dawn = datetime(2026, 5, 27, 5, 30, tzinfo=tz)
        self.assertFalse(planner.should_run_automatic_reconcile(now_local=before_dawn))
        self.assertTrue(planner.should_run_automatic_reconcile(now_local=after_dawn))

    @patch.dict("os.environ", {"SHORTS_BREAKING_MIN_SCORE": "60"}, clear=False)
    @patch("newsica.shorts.daily_planner.add_plan_item", return_value=True)
    @patch("newsica.shorts.daily_planner.list_plan_items", return_value=[])
    @patch("newsica.shorts.daily_planner.get_daily_plan", return_value={"target_date": "2026-05-27"})
    def test_breaking_extra_inserted_when_high_gravity_candidate_exists(
        self,
        _mock_plan,
        _mock_items,
        mock_add_item,
    ):
        planner = DailyShortsPlanner()
        tz = ZoneInfo(planner.timezone)
        now_local = datetime(2026, 5, 27, 12, 0, tzinfo=tz)
        planner._load_recent_news = lambda: [
            {
                "title": "Terremoto e vittime in città",
                "summary": "Forte scossa e allerta nazionale",
                "source": "ansa_ultimora",
                "published": "2026-05-27T11:30:00+02:00",
            }
        ]

        result = planner.ensure_breaking_extra_if_needed(now_local=now_local)
        self.assertEqual(result["status"], "planned")
        self.assertTrue(mock_add_item.called)

    @patch.dict("os.environ", {"SHORTS_BREAKING_MIN_SCORE": "95"}, clear=False)
    @patch("newsica.shorts.daily_planner.add_plan_item", return_value=True)
    @patch("newsica.shorts.daily_planner.list_plan_items", return_value=[])
    @patch("newsica.shorts.daily_planner.get_daily_plan", return_value={"target_date": "2026-05-27"})
    def test_breaking_extra_skipped_when_score_below_threshold(
        self,
        _mock_plan,
        _mock_items,
        mock_add_item,
    ):
        planner = DailyShortsPlanner()
        tz = ZoneInfo(planner.timezone)
        now_local = datetime(2026, 5, 27, 12, 0, tzinfo=tz)
        planner._load_recent_news = lambda: [
            {
                "title": "Accordo politico in Parlamento",
                "summary": "Intesa dopo lunga trattativa",
                "source": "ansa_ultimora",
                "published": "2026-05-27T11:45:00+02:00",
            }
        ]

        result = planner.ensure_breaking_extra_if_needed(now_local=now_local)
        self.assertEqual(result["status"], "below_threshold")
        self.assertFalse(mock_add_item.called)


if __name__ == "__main__":
    unittest.main()
