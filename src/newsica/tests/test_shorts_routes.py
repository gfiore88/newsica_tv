import unittest
from unittest.mock import patch

from flask import Flask

from newsica.web.shorts_routes import register_shorts_routes


class _PlannerStub:
    def reconcile_today_plan(self, force=False):
        return {"status": "planned", "target_date": "2026-05-28", "item_count": 0}


class TestShortsRoutes(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        register_shorts_routes(self.app, base_dir="/tmp", shorts_daily_planner=_PlannerStub())
        self.client = self.app.test_client()

    def test_registers_expected_shorts_endpoints(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/api/generate_short", rules)
        self.assertIn("/api/shorts_publish", rules)
        self.assertIn("/api/shorts_plan_today", rules)
        self.assertIn("/api/shorts_plan_rebuild", rules)
        self.assertIn("/api/shorts_plan_process_once", rules)
        self.assertIn("/api/shorts_library", rules)
        self.assertIn("/api/shorts_video/<path:filename>", rules)
        self.assertIn("/api/shorts_delete", rules)

    @patch("newsica.web.shorts_routes.process_one_planned_short_item", return_value={"status": "idle", "message": "ok"})
    def test_plan_process_once_endpoint_uses_executor(self, _mock_executor):
        resp = self.client.post("/api/shorts_plan_process_once", json={})
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload.get("status"), "idle")


if __name__ == "__main__":
    unittest.main()

