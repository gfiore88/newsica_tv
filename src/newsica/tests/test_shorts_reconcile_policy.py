import datetime
import unittest
from unittest.mock import patch

from newsica.broadcast.shorts_reconcile_policy import ShortsReconcilePolicy


class _PlannerStub:
    timezone = "Europe/Rome"

    def __init__(self):
        self.now = datetime.datetime(2026, 5, 28, 7, 0, 0)
        self.reconcile_calls = 0
        self.breaking_calls = 0
        self.should_run = True

    def now_local(self):
        return self.now

    def should_run_automatic_reconcile(self, now_local):
        return self.should_run

    def get_today_dawn(self, now_local):
        return now_local.replace(hour=6, minute=0)

    def reconcile_today_plan(self, force=False):
        self.reconcile_calls += 1
        return {"status": "planned"}

    def ensure_breaking_extra_if_needed(self):
        self.breaking_calls += 1
        return {"status": "idle"}


class TestShortsReconcilePolicy(unittest.TestCase):
    def test_daily_reconcile_runs_once_per_day(self):
        planner = _PlannerStub()
        policy = ShortsReconcilePolicy(planner, breaking_probe_interval_seconds=600)

        policy.reconcile_daily_if_needed()
        policy.reconcile_daily_if_needed()

        self.assertEqual(planner.reconcile_calls, 1)

    def test_breaking_reconcile_respects_probe_interval(self):
        planner = _PlannerStub()
        policy = ShortsReconcilePolicy(planner, breaking_probe_interval_seconds=600)

        with patch("newsica.broadcast.shorts_reconcile_policy.time.time", side_effect=[1000, 1010, 1705]):
            policy.reconcile_breaking_if_needed()
            policy.reconcile_breaking_if_needed()
            policy.reconcile_breaking_if_needed()

        self.assertEqual(planner.breaking_calls, 2)


if __name__ == "__main__":
    unittest.main()
