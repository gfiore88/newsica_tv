import unittest

from overlay_agent import get_schedule_anchor_index, read_schedule_items


class TestOverlayTimeline(unittest.TestCase):
    def test_anchor_uses_current_scheduled_slot_before_next_start(self):
        times = ["17:00", "18:30", "20:00"]
        state = {
            "scheduled_slot": "17:00",
            "next_start": "18:30",
        }

        anchor = get_schedule_anchor_index(state, times)

        self.assertEqual(anchor, 0)

    def test_read_schedule_items_starts_from_current_slot(self):
        schedule_data = {
            "17:00": {"title": "Rock & Roll Arena"},
            "18:30": {"title": "Newsica Podcast"},
            "20:00": {"title": "Newsica Sera"},
        }
        state = {
            "scheduled_slot": "17:00",
            "next_start": "18:30",
        }

        items = read_schedule_items(state, schedule_data, max_items=3)

        self.assertEqual([item["time"] for item in items], ["17:00", "18:30", "20:00"])


if __name__ == "__main__":
    unittest.main()
