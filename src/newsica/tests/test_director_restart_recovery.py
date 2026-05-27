import unittest
from unittest.mock import patch

from director import build_restart_recovery_state


class TestDirectorRestartRecovery(unittest.TestCase):

    # --- Nuovi test per la regressione music_only → silenzio post-restart ---

    def test_restart_during_music_only_with_stale_voice_segment_goes_offline(self):
        """
        Regressione: il jingle di apertura di un blocco music_only scriveva
        current_segment='voice_part_1' nello stato runtime. Dopo un restart,
        questo segmento veniva preservato → _progress_current_block() tornava
        TriggerNextBlockEvent() in loop → silenzio totale sulla live.

        Fix: i blocchi music_only vanno sempre OFFLINE al restart, così
        _initialize_scheduled_block() viene chiamato e il PlayoutPlanner
        mette subito in coda un PlayMusicDeadlineEvent.
        """
        state = {
            "status": "ON_AIR",
            "current_block": "music_only",
            "current_title": "Baila Newsica",
            "current_segment": "voice_part_1",   # segmento spurio pre-fix
            "scheduled_slot": "13:30",
        }

        recovered = build_restart_recovery_state(
            state,
            "13:30",
            "2026-05-26T14:15:00",
        )

        self.assertEqual(
            recovered["status"], "OFFLINE",
            "Un blocco music_only deve essere OFFLINE dopo il restart "
            "per forzare la re-inizializzazione immediata senza silenzio.",
        )

    @patch("director.scheduler.get_current_schedule")
    def test_restart_during_music_only_music_rotation_realigns_to_schedule(self, mock_schedule):
        """
        Anche con current_segment='music_rotation' (già in rotazione musicale),
        al restart riallineiamo titolo/tipo/tema al palinsesto dello slot
        corrente invece di preservare uno stato stantio.
        """
        mock_schedule.return_value = {
            "13:30": {"title": "Baila Newsica", "type": "music_only", "theme": "latin/reggaeton/dembow"}
        }
        state = {
            "status": "ON_AIR",
            "current_block": "music_only",
            "current_title": "Baila Newsica",
            "current_segment": "music_rotation",
            "scheduled_slot": "13:30",
        }

        recovered = build_restart_recovery_state(
            state,
            "13:30",
            "2026-05-26T14:15:00",
        )

        self.assertEqual(recovered["status"], "ON_AIR")
        self.assertEqual(recovered["current_block"], "music_only")
        self.assertEqual(recovered["current_title"], "Baila Newsica")
        self.assertEqual(recovered["theme"], "latin/reggaeton/dembow")

    # --- Test pre-esistenti (invariati) ---

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

    def test_restart_preserves_music_rotation_segment_as_is(self):
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

    @patch("director.scheduler.get_current_schedule")
    def test_restart_realigns_stale_immediate_state_to_current_slot_show(self, mock_schedule):
        mock_schedule.return_value = {
            "17:00": {"title": "Rock & Roll Arena", "type": "music_only", "theme": "rock"}
        }
        state = {
            "status": "ON_AIR",
            "current_block": "wellness",
            "current_title": "Pausa Benessere",
            "current_segment": "music_rotation_until_deadline",
            "scheduled_slot": "17:00",
        }

        recovered = build_restart_recovery_state(
            state,
            "17:00",
            "2026-05-26T18:12:35",
        )

        self.assertEqual(recovered["status"], "ON_AIR")
        self.assertEqual(recovered["current_block"], "music_only")
        self.assertEqual(recovered["current_title"], "Rock & Roll Arena")
        self.assertEqual(recovered["theme"], "rock")

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
