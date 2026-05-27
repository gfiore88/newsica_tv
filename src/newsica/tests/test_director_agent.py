import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from newsica.broadcast.director_agent import DirectorAgent
from newsica.audio.music_library import GENERIC_THEMELESS_MUSIC_TITLE
from newsica.domain.playout_events import (
    PlayJingleEvent,
    PlayMusicDeadlineEvent,
    PlayMusicEvent,
    PlaySilenceFallbackEvent,
    TriggerNextBlockEvent,
    PlayVoiceEvent,
)


class TestDirectorAgent(unittest.TestCase):
    def setUp(self):
        self.audit_tmp = tempfile.TemporaryDirectory()
        self.previous_audit_log = os.environ.get("NEWSICA_AUDIT_LOG_FILE")
        os.environ["NEWSICA_AUDIT_LOG_FILE"] = os.path.join(self.audit_tmp.name, "audit_trail.log")
        self.mock_playout = MagicMock()
        self.mock_playout.get_random_music.return_value = "assets/music/track_test.mp3"
        self.director = DirectorAgent(self.mock_playout)

    def tearDown(self):
        if self.previous_audit_log is None:
            os.environ.pop("NEWSICA_AUDIT_LOG_FILE", None)
        else:
            os.environ["NEWSICA_AUDIT_LOG_FILE"] = self.previous_audit_log
        self.audit_tmp.cleanup()

    @patch("newsica.broadcast.director_agent.write_state_files")
    @patch("newsica.broadcast.director_agent.get_jingle_for_block")
    def test_initialize_podcast_block_returns_jingle_event(self, mock_get_jingle, mock_write_state):
        mock_get_jingle.return_value = ("assets/jingles/jingle_podcast.mp3", "podcast_jingle")

        action = self.director._initialize_scheduled_block(
            block_type="podcast",
            title="Newsica Podcast",
            next_title="Meteo",
            next_time="16:00",
            current_time="15:00",
        )

        self.assertIsInstance(action, PlayJingleEvent)
        self.assertEqual(action.file, "assets/jingles/jingle_podcast.mp3")
        self.assertEqual(action.next_segment, "intro")
        mock_write_state.assert_called_once()

    @patch("newsica.broadcast.director_agent.get_current_state")
    @patch("newsica.broadcast.director_agent.write_state_files")
    def test_notify_interrupt_high_severity_returns_jingle_event(self, mock_write_state, mock_get_state):
        mock_get_state.return_value = {
            "status": "ON_AIR",
            "current_block": "news",
            "current_title": "Chiara News",
            "scheduled_slot": "15:00",
        }

        action = self.director.notify_interrupt(
            reason="Terremoto di forte intensità rilevato",
            severity_score=95,
        )

        self.assertIsInstance(action, PlayJingleEvent)
        self.assertEqual(action.label, "jingle_straordinaria")
        written_state = mock_write_state.call_args[0][0]
        self.assertEqual(written_state["status"], "SPECIAL_BROADCAST")
        self.assertEqual(written_state["current_block"], "trasmissione_straordinaria")
        self.assertEqual(written_state["interrupted_block"], "news")
        self.assertEqual(written_state["severity_score"], 95)

    @patch("newsica.broadcast.director_agent.get_current_state")
    @patch("newsica.broadcast.director_agent.write_state_files")
    @patch("newsica.broadcast.director_agent.get_current_block_info")
    @patch("newsica.broadcast.director_agent.schedule_deadline")
    def test_restore_after_interrupt_more_than_threshold_remaining(
        self, mock_deadline, mock_block_info, mock_write_state, mock_get_state
    ):
        mock_get_state.return_value = {
            "status": "SPECIAL_BROADCAST",
            "interrupted_slot": "15:00",
            "interrupted_block": "sport",
            "interrupted_title": "Leo Sport",
            "next_block": "Meteo",
            "next_start": "15:30",
        }
        mock_block_info.return_value = ("sport", "Leo Sport", "Meteo", "15:30", "15:00", 0)
        mock_deadline.return_value = datetime.datetime.now() + datetime.timedelta(minutes=25)

        self.director.handle_restore_after_interrupt()

        restored_state = mock_write_state.call_args[0][0]
        self.assertEqual(restored_state["status"], "ON_AIR")
        self.assertEqual(restored_state["current_block"], "sport")
        self.assertEqual(restored_state["current_segment"], "music_rotation_until_deadline")

    def test_handle_podcast_progression_plays_ready_audio_with_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            ready_dir = os.path.join(tmp, "assets", "ready", "1500")
            os.makedirs(ready_dir, exist_ok=True)
            with open(os.path.join(ready_dir, "audio.wav"), "wb") as f:
                f.write(b"audio")
            with open(os.path.join(ready_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"character": "podcast", "title": "Newsica Podcast - Focus"}, f)

            state = {
                "status": "ON_AIR",
                "scheduled_slot": "15:00",
                "current_segment": "intro",
                "podcast_played": False,
            }

            with patch("newsica.broadcast.director_agent.RUNTIME_DIR", tmp), patch(
                "newsica.broadcast.director_agent.write_state_files"
            ) as mock_write_state:
                action = self.director._handle_podcast_progression(
                    state, "Newsica Podcast", "intro", "16:00"
                )

            self.assertIsInstance(action, PlayVoiceEvent)
            self.assertEqual(action.character, "podcast")
            self.assertTrue(state["podcast_played"])
            mock_write_state.assert_called_once()

    @patch("newsica.broadcast.director_agent.schedule_deadline")
    @patch("newsica.broadcast.director_agent.get_wallclock_schedule_key")
    @patch("newsica.broadcast.director_agent.write_state_files")
    def test_podcast_rotation_returns_music_event_with_ai_trigger(
        self, mock_write_state, mock_wallclock, mock_deadline
    ):
        mock_wallclock.return_value = "15:00"
        mock_deadline.return_value = datetime.datetime.now() + datetime.timedelta(minutes=15)
        state = {
            "status": "ON_AIR",
            "scheduled_slot": "15:00",
            "current_segment": "music_rotation_until_deadline",
            "theme": "cinema",
            "podcast_played": True,
        }

        action = self.director._handle_podcast_progression(
            state, "Newsica Podcast", "music_rotation_until_deadline", "16:00"
        )

        self.assertIsInstance(action, PlayMusicEvent)
        self.assertEqual(action.file, "assets/music/track_test.mp3")
        self.assertTrue(action.trigger_ai_music_gen)
        self.assertEqual(action.theme, "cinema")

    @patch("newsica.broadcast.director_agent.get_wallclock_schedule_key")
    @patch("newsica.broadcast.director_agent.schedule_deadline")
    def test_standard_block_progression_uses_deadline_event(self, mock_deadline, mock_wallclock):
        mock_wallclock.return_value = "14:00"
        mock_deadline.return_value = datetime.datetime.now() + datetime.timedelta(minutes=10)
        state = {
            "status": "ON_AIR",
            "scheduled_slot": "14:00",
            "current_segment": "music_rotation_until_deadline",
            "theme": "calcio",
        }

        action = self.director._progress_current_block(
            state, "sport", "Pomeriggio Sport", "Meteo", "15:00", "14:00"
        )

        self.assertIsInstance(action, PlayMusicDeadlineEvent)

    @patch("newsica.broadcast.director_agent.get_wallclock_schedule_key")
    @patch("newsica.broadcast.director_agent.schedule_deadline")
    def test_standard_block_fallback_music_rotation_continues_until_deadline(self, mock_deadline, mock_wallclock):
        mock_wallclock.return_value = "09:00"
        mock_deadline.return_value = datetime.datetime.now() + datetime.timedelta(minutes=10)
        state = {
            "status": "ON_AIR",
            "scheduled_slot": "09:00",
            "current_segment": "music_rotation_until_deadline",
            "theme": None,
        }

        action = self.director._progress_current_block(
            state, "flash_60s", "Mondo in 60 Secondi", "Meteo Update", "10:00", "09:00"
        )

        self.assertIsInstance(action, PlayMusicDeadlineEvent)

    @patch("newsica.broadcast.director_agent.get_wallclock_schedule_key")
    @patch("newsica.broadcast.director_agent.schedule_deadline")
    def test_music_only_progression_uses_deadline_event_until_slot_end(self, mock_deadline, mock_wallclock):
        mock_wallclock.return_value = "17:00"
        mock_deadline.return_value = datetime.datetime.now() + datetime.timedelta(minutes=10)
        state = {
            "status": "ON_AIR",
            "scheduled_slot": "17:00",
            "current_segment": "music_rotation",
            "theme": None,
        }

        action = self.director._progress_current_block(
            state, "music_only", "Newsica Music Flow", "Newsica Podcast", "18:30", "17:00"
        )

        self.assertIsInstance(action, PlayMusicDeadlineEvent)

    @patch("newsica.broadcast.director_agent.get_wallclock_schedule_key")
    @patch("newsica.broadcast.director_agent.schedule_deadline")
    def test_music_only_progression_triggers_next_block_at_deadline(self, mock_deadline, mock_wallclock):
        mock_wallclock.return_value = "17:00"
        mock_deadline.return_value = datetime.datetime.now() - datetime.timedelta(seconds=1)
        state = {
            "status": "ON_AIR",
            "scheduled_slot": "17:00",
            "current_segment": "music_rotation",
            "theme": None,
        }

        action = self.director._progress_current_block(
            state, "music_only", "Newsica Music Flow", "Newsica Podcast", "18:30", "17:00"
        )

        self.assertIsInstance(action, TriggerNextBlockEvent)

    def test_special_broadcast_without_bulletin_waits_with_silence_event(self):
        state = {"current_segment": "intro"}

        with patch("newsica.broadcast.director_agent.TMP_DIR", self.audit_tmp.name), patch(
            "newsica.broadcast.director_agent.ASSETS_DIR", self.audit_tmp.name
        ):
            action = self.director._handle_special_broadcast(state)

        self.assertIsInstance(action, PlaySilenceFallbackEvent)
        self.assertEqual(action.seconds, 5)

    def test_music_slot_guardrail_degrades_title_when_theme_catalog_missing(self):
        mock_library = MagicMock()
        mock_library.has_minimum_theme_catalog.return_value = False
        mock_library.count_ai_tracks_for_theme.return_value = 1

        with patch("newsica.broadcast.director_agent.MusicLibrary", return_value=mock_library):
            title, theme = self.director._resolve_music_slot_editorial_guardrail(
                "music_only",
                "Rock & Roll Arena",
                "rock",
            )

        self.assertEqual(title, GENERIC_THEMELESS_MUSIC_TITLE)
        self.assertIsNone(theme)

    @patch("newsica.broadcast.director_agent.write_state_files")
    @patch("schedule_generator.get_current_schedule")
    @patch("newsica.broadcast.director_agent.get_current_block_info")
    @patch("newsica.broadcast.director_agent.get_wallclock_schedule_key")
    def test_restore_after_immediate_event_realigns_to_scheduled_theme(
        self,
        mock_wallclock,
        mock_block_info,
        mock_schedule,
        mock_write_state,
    ):
        mock_wallclock.return_value = "17:00"
        mock_block_info.return_value = ("music_only", "Rock & Roll Arena", "Newsica Podcast", "18:30", "17:00", 0)
        mock_schedule.return_value = {
            "17:00": {"title": "Rock & Roll Arena", "type": "music_only", "theme": "rock"},
            "18:30": {"title": "Newsica Podcast", "type": "podcast"},
        }

        with patch.object(
            self.director,
            "_resolve_music_slot_editorial_guardrail",
            return_value=("Rock & Roll Arena", "rock"),
        ):
            self.director.restore_after_immediate_event(
                {
                    "scheduled_slot": "17:00",
                    "current_block": "wellness",
                    "current_title": "Pausa Benessere",
                }
            )

        restored_state = mock_write_state.call_args[0][0]
        self.assertEqual(restored_state["current_block"], "music_only")
        self.assertEqual(restored_state["current_title"], "Rock & Roll Arena")
        self.assertEqual(restored_state["theme"], "rock")
        self.assertEqual(restored_state["current_segment"], "music_rotation_until_deadline")

    @patch("newsica.broadcast.director_agent.write_state_files")
    @patch("newsica.broadcast.director_agent.get_wallclock_schedule_key")
    def test_restore_after_immediate_event_goes_offline_if_slot_changed(self, mock_wallclock, mock_write_state):
        mock_wallclock.return_value = "18:30"

        self.director.restore_after_immediate_event(
            {
                "scheduled_slot": "17:00",
                "current_block": "wellness",
                "current_title": "Pausa Benessere",
            }
        )

        mock_write_state.assert_called_once_with({"status": "OFFLINE"})


if __name__ == "__main__":
    unittest.main()
