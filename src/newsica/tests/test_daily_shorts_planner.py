import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from newsica.shorts.daily_planner import DailyShortsPlanner


class TestDailyShortsPlanner(unittest.TestCase):
    @patch("newsica.shorts.daily_planner.calculate_heuristic_score")
    def test_build_items_enforces_always_constraints_and_conditional_relevance(self, mock_score):
        def score_side_effect(title, summary, category=None):
            mapping = {
                ("Governo approva nuova manovra", "news"): 95,
                ("Nuovo modello AI rivoluziona i chip", "news"): 50,
                ("Nuovo modello AI rivoluziona i chip", "tech"): 92,
                ("Trend social curioso del giorno", "funfact"): 88,
                ("Alluvione con allerta rossa in Liguria", "meteo"): 80,
                ("Finale europea decisa ai rigori", "sport"): 70,
                ("Routine benessere per migliorare il sonno", "wellness"): 68,
            }
            return mapping.get((title, category), 10)

        mock_score.side_effect = score_side_effect
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

    def test_pick_candidate_returns_none_for_duplicate_titles(self):
        planner = DailyShortsPlanner()
        candidates = [
            {"title": "Amazon lancia nuova flotta", "summary": "Consegne con droni", "source": "ansa_tecnologia"},
        ]
        selected_titles = {"amazon lancia nuova flotta"}
        
        picked = planner._pick_candidate(candidates, selected_titles)
        self.assertIsNone(picked, "Dovrebbe ritornare None se l'articolo è già stato selezionato per prevenire duplicati.")

    @patch("newsica.shorts.daily_planner.calculate_heuristic_score")
    def test_build_items_skips_mode_when_only_candidate_is_already_used(self, mock_score):
        def score_side_effect(title, summary, category=None):
            mapping = {
                ("Amazon lancia nuova flotta", "news"): 10,
                ("Amazon lancia nuova flotta", "tech"): 95,
                ("Amazon lancia nuova flotta", "funfact"): 90,
                ("Notizia generale unica", "news"): 98,
            }
            return mapping.get((title, category), 5)

        mock_score.side_effect = score_side_effect
        planner = DailyShortsPlanner()
        fake_news = [
            {"title": "Amazon lancia nuova flotta", "summary": "Consegne con droni", "source": "ansa_tecnologia"},
            {"title": "Notizia generale unica", "summary": "Cronaca pulita", "source": "sky_tg24"},
        ]
        # tech e funfact condividono lo stesso unico candidato. Il secondo mode che
        # resta senza contenuti unici deve essere saltato, non riempito con una news generica.
        items = planner._build_items(fake_news, target_day=date(2026, 5, 27))

        items_by_mode = {item["mode"]: item for item in items}
        titles = [item["source_title"] for item in items if item["source_title"]]
        self.assertEqual(len(titles), len(set(titles)), "Gli articoli programmati non devono contenere duplicati.")
        self.assertIn("funfact", items_by_mode)
        self.assertEqual(items_by_mode["funfact"]["source_title"], "Amazon lancia nuova flotta")
        self.assertNotIn("tech", items_by_mode)
        self.assertIn("Notizia generale unica", titles)


if __name__ == "__main__":
    unittest.main()
