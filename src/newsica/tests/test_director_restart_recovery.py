import unittest

from director import build_restart_recovery_state


class TestDirectorRestartRecovery(unittest.TestCase):
    def test_restart_during_podcast_degrades_to_music_without_replay(self):
        state = {
            "status": "ON_AIR",
            "current_block": "podcast",
            "current_title": "Newsica Podcast",
            "current_segment": "podcast_playing",
            "scheduled_slot": "15:00",
            "podcast_played": True,
        }

        recovered = build_restart_recovery_state(
            state,
            "15:00",
            "2026-05-25T15:52:30",
        )

        self.assertEqual(recovered["status"], "ON_AIR")
        self.assertEqual(recovered["current_segment"], "music_rotation_until_deadline")
        self.assertTrue(recovered["podcast_played"])
        self.assertEqual(recovered["scheduled_slot"], "15:00")

    def test_restart_during_standard_voice_segment_degrades_to_music(self):
        state = {
            "status": "ON_AIR",
            "current_block": "sport",
            "current_title": "Pomeriggio Sport",
            "current_segment": "voice_part_2",
            "scheduled_slot": "14:00",
        }

        recovered = build_restart_recovery_state(
            state,
            "14:00",
            "2026-05-25T14:18:15",
        )

        self.assertEqual(recovered["current_segment"], "music_rotation_until_deadline")
        self.assertEqual(recovered["current_block"], "sport")

    def test_restart_preserves_music_segment_as_is(self):
        state = {
            "status": "ON_AIR",
            "current_block": "sport",
            "current_title": "Pomeriggio Sport",
            "current_segment": "music_rotation_until_deadline",
            "scheduled_slot": "14:00",
        }

        recovered = build_restart_recovery_state(
            state,
            "14:00",
            "2026-05-25T14:18:15",
        )

        self.assertEqual(recovered["current_segment"], "music_rotation_until_deadline")

    def test_restart_with_stale_slot_goes_offline(self):
        state = {
            "status": "ON_AIR",
            "current_block": "sport",
            "current_segment": "voice_part_1",
            "scheduled_slot": "14:00",
        }

        recovered = build_restart_recovery_state(
            state,
            "16:00",
            "2026-05-25T16:00:00",
        )

        self.assertEqual(recovered["status"], "OFFLINE")

    def test_restart_preserves_special_broadcast_context(self):
        state = {
            "status": "SPECIAL_BROADCAST",
            "current_block": "trasmissione_straordinaria",
            "current_segment": "broadcast_body",
        }

        recovered = build_restart_recovery_state(
            state,
            "15:00",
            "2026-05-25T15:52:30",
        )

        self.assertEqual(recovered["status"], "SPECIAL_BROADCAST")
        self.assertEqual(recovered["current_segment"], "broadcast_waiting")


if __name__ == "__main__":
    unittest.main()
