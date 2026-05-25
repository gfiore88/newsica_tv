import unittest

from director import build_ordinary_breaking_state


class TestDirectorBreakingState(unittest.TestCase):
    def test_ordinary_breaking_preserves_slot_context(self):
        prev_state = {
            "status": "ON_AIR",
            "current_block": "sport",
            "current_title": "Pomeriggio Sport - Parte 2",
            "current_segment": "voice_part_2",
            "scheduled_slot": "14:00",
            "theme": "calcio mercato",
        }

        state = build_ordinary_breaking_state(prev_state, "2026-05-25T14:13:12")

        self.assertEqual(state["status"], "ON_AIR")
        self.assertEqual(state["current_block"], "breaking_news")
        self.assertEqual(state["current_title"], "ULTIM'ORA")
        self.assertEqual(state["current_segment"], "voice_part_2")
        self.assertEqual(state["scheduled_slot"], "14:00")
        self.assertEqual(state["theme"], "calcio mercato")
        self.assertEqual(state["last_update"], "2026-05-25T14:13:12")


if __name__ == "__main__":
    unittest.main()
