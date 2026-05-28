import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from newsica.storage import database
from newsica.storage.repositories.shorts_plan_repository import (
    add_plan_item,
    get_pending_generation_items,
    list_plan_items,
    save_daily_plan,
)


class TestShortsPlanRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "newsica_test.db")
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_schema()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_get_pending_generation_items_filters_by_due_window(self):
        target_date = "2026-05-27"
        now_utc = datetime.now(timezone.utc)
        due_soon = (now_utc + timedelta(minutes=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
        due_late = (now_utc + timedelta(minutes=190)).strftime("%Y-%m-%dT%H:%M:%SZ")

        save_daily_plan(
            target_date=target_date,
            status="planned",
            reason="test",
            plan_payload={"target_date": target_date},
            items=[
                {
                    "mode": "news",
                    "rule_type": "always",
                    "priority": 100,
                    "source_title": "News 1",
                    "source_summary": "Summary 1",
                    "source_score": 80,
                    "scheduled_for": {"youtube": {"utc": due_late, "local": due_late}},
                    "status": "planned",
                },
                {
                    "mode": "tech",
                    "rule_type": "always",
                    "priority": 90,
                    "source_title": "News 2",
                    "source_summary": "Summary 2",
                    "source_score": 70,
                    "scheduled_for": {"youtube": {"utc": due_soon, "local": due_soon}},
                    "status": "planned",
                },
            ],
        )

        pending = get_pending_generation_items(limit=5, due_within_minutes=60)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["mode"], "tech")

    def test_add_plan_item_inserts_breaking_extra(self):
        target_date = "2026-05-27"
        save_daily_plan(
            target_date=target_date,
            status="planned",
            reason="test",
            plan_payload={"target_date": target_date},
            items=[],
        )

        ok = add_plan_item(
            target_date,
            {
                "mode": "breaking",
                "rule_type": "extra",
                "reason": "breaking_extra:score=88",
                "priority": 140,
                "source_title": "Breaking test",
                "source_summary": "Summary",
                "source_score": 88,
                "scheduled_for": {"youtube": {"utc": "2026-05-27T10:00:00Z", "local": "2026-05-27T12:00:00+02:00"}},
                "status": "planned",
            },
        )
        self.assertTrue(ok)
        items = list_plan_items(target_date)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["mode"], "breaking")


if __name__ == "__main__":
    unittest.main()

