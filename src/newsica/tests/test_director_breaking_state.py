import unittest
from unittest.mock import MagicMock

import director
from director import build_ordinary_breaking_state, handle_ordinary_breaking_news, merge_display_state


class TestDirectorBreakingState(unittest.TestCase):
    def setUp(self):
        director.breaking_news_active = False

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

    def test_handle_ordinary_breaking_news_preserves_and_restores_state(self):
        prev_state = {
            "status": "ON_AIR",
            "current_block": "sport",
            "current_title": "Pomeriggio Sport - Parte 2",
            "current_segment": "voice_part_2",
            "scheduled_slot": "14:00",
            "theme": "calcio mercato",
        }
        fifo_writer = MagicMock()
        written_states = []
        restored = []

        proc = MagicMock()
        proc.stdout.read.side_effect = [b"abc", b"def", b""]
        proc.wait.return_value = 0
        popen_factory = MagicMock(return_value=proc)

        def state_writer(state):
            written_states.append(state)

        def restore_fn(state, label):
            restored.append((state, label))

        handle_ordinary_breaking_news(
            fifo_writer,
            "/tmp/breaking.wav",
            now_ts="2026-05-25T14:13:12",
            state_reader=lambda: prev_state,
            state_writer=state_writer,
            restore_fn=restore_fn,
            popen_factory=popen_factory,
        )

        fifo_writer.apply_preventive_fade_out_and_write.assert_called_once()
        fifo_writer.write_chunk.assert_any_call(b"abc")
        fifo_writer.write_chunk.assert_any_call(b"def")
        self.assertEqual(len(written_states), 1)
        self.assertEqual(written_states[0]["current_block"], "breaking_news")
        self.assertEqual(written_states[0]["current_segment"], "voice_part_2")
        self.assertEqual(written_states[0]["scheduled_slot"], "14:00")
        self.assertEqual(restored, [(prev_state, "breaking news")])
        self.assertFalse(director.breaking_news_active)

    def test_merge_display_state_preserves_runtime_machine_fields(self):
        existing_state = {
            "status": "ON_AIR",
            "current_block": "news",
            "current_title": "Pranzo News",
            "current_segment": "voice_part_1",
            "scheduled_slot": "13:00",
            "next_block": "Baila Newsica",
        }
        incoming_state = {
            "status": "ON_AIR",
            "current_block": "music_only",
            "current_title": "Baila Newsica",
            "next_block": "Oggi alle 14",
            "next_start": "14:30",
            "scheduled_slot": "13:30",
            "current_segment": "music_rotation_until_deadline",
        }

        merged = merge_display_state(existing_state, incoming_state)

        self.assertEqual(merged["status"], "ON_AIR")
        self.assertEqual(merged["current_block"], "music_only")
        self.assertEqual(merged["current_title"], "Baila Newsica")
        self.assertEqual(merged["next_block"], "Oggi alle 14")
        self.assertEqual(merged["scheduled_slot"], "13:00")
        self.assertEqual(merged["current_segment"], "voice_part_1")

    def test_merge_display_state_does_not_write_into_offline_state(self):
        existing_state = {
            "status": "OFFLINE",
            "last_update": "2026-05-26T13:30:00",
        }
        incoming_state = {
            "current_block": "music_only",
            "current_title": "Baila Newsica",
            "next_block": "Oggi alle 14",
        }

        merged = merge_display_state(existing_state, incoming_state)

        self.assertEqual(merged, existing_state)


if __name__ == "__main__":
    unittest.main()
