import unittest
from unittest.mock import patch

from newsica.shorts.plan_executor import process_one_planned_short_item


class TestShortsPlanExecutor(unittest.TestCase):
    @patch("newsica.shorts.plan_executor.get_pending_generation_items", return_value=[])
    def test_process_one_planned_short_item_returns_idle_when_queue_empty(self, mock_pending):
        result = process_one_planned_short_item(due_within_minutes=42)
        self.assertEqual(result.get("status"), "idle")
        mock_pending.assert_called_once_with(limit=1, due_within_minutes=42)


if __name__ == "__main__":
    unittest.main()

