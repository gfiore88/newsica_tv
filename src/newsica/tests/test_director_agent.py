import unittest
from unittest.mock import MagicMock, patch, mock_open
import datetime
import json
import os

from newsica.broadcast.director_agent import DirectorAgent

class TestDirectorAgent(unittest.TestCase):
    def setUp(self):
        self.mock_playout = MagicMock()
        self.mock_playout.get_random_music.return_value = "assets/music/track_test.mp3"
        self.director = DirectorAgent(self.mock_playout)

    @patch("newsica.broadcast.director_agent.write_state_files")
    @patch("newsica.broadcast.director_agent.get_jingle_for_block")
    def test_initialize_scheduled_block(self, mock_get_jingle, mock_write_state):
        mock_get_jingle.return_value = ("assets/jingles/jingle_sport.mp3", "sport_jingle")
        
        action = self.director._initialize_scheduled_block(
            block_type="sport",
            title="Leo Sport",
            next_title="Meteo",
            next_time="15:30",
            current_time="15:00"
        )
        
        # Controlla la scrittura dello stato
        mock_write_state.assert_called_once()
        written_state = mock_write_state.call_args[0][0]
        self.assertEqual(written_state["status"], "ON_AIR")
        self.assertEqual(written_state["current_block"], "sport")
        self.assertEqual(written_state["current_title"], "Leo Sport")
        
        # Controlla l'azione restituita
        self.assertEqual(action["action"], "PLAY_JINGLE")
        self.assertEqual(action["file"], "assets/jingles/jingle_sport.mp3")
        self.assertEqual(action["next_segment"], "intro")

    @patch("newsica.broadcast.director_agent.get_current_state")
    @patch("newsica.broadcast.director_agent.write_state_files")
    def test_notify_interrupt_high_severity(self, mock_write_state, mock_get_state):
        mock_get_state.return_value = {
            "status": "ON_AIR",
            "current_block": "news",
            "current_title": "Chiara News",
            "scheduled_slot": "15:00"
        }
        
        action = self.director.notify_interrupt(
            reason="Terremoto di forte intensità rilevato",
            severity_score=95
        )
        
        # Controlla la scrittura dello stato speciale
        mock_write_state.assert_called_once()
        written_state = mock_write_state.call_args[0][0]
        self.assertEqual(written_state["status"], "SPECIAL_BROADCAST")
        self.assertEqual(written_state["current_block"], "trasmissione_straordinaria")
        self.assertEqual(written_state["interrupted_block"], "news")
        self.assertEqual(written_state["severity_score"], 95)
        
        # Controlla l'azione di riproduzione del jingle straordinario
        self.assertEqual(action["action"], "PLAY_JINGLE")
        self.assertEqual(action["label"], "jingle_straordinaria")

    @patch("newsica.broadcast.director_agent.get_current_state")
    @patch("newsica.broadcast.director_agent.write_state_files")
    @patch("newsica.broadcast.director_agent.get_current_block_info")
    @patch("newsica.broadcast.director_agent.schedule_deadline")
    def test_restore_after_interrupt_more_than_40_percent_remaining(self, mock_deadline, mock_block_info, mock_write_state, mock_get_state):
        # Ipotizziamo che lo slot sia iniziato alle 15:00 e scada alle 15:30.
        # Durata totale = 30 min (1800 secondi). 40% = 12 minuti.
        # Se ora sono le 15:05, mancano 25 minuti (>= 40%). Dovrebbe ripristinare.
        
        mock_get_state.return_value = {
            "status": "SPECIAL_BROADCAST",
            "interrupted_slot": "15:00",
            "interrupted_block": "sport",
            "interrupted_title": "Leo Sport",
            "next_block": "Meteo",
            "next_start": "15:30"
        }
        
        mock_block_info.return_value = ("sport", "Leo Sport", "Meteo", "15:30", "15:00", 0)
        
        # Imposta la deadline del prossimo blocco a +25 minuti da adesso
        now = datetime.datetime.now()
        mock_deadline.return_value = now + datetime.timedelta(minutes=25)
        
        self.director.handle_restore_after_interrupt()
        
        # Controlla che lo stato sia stato ripristinato a ON_AIR su quel blocco
        mock_write_state.assert_called_once()
        restored_state = mock_write_state.call_args[0][0]
        self.assertEqual(restored_state["status"], "ON_AIR")
        self.assertEqual(restored_state["current_block"], "sport")
        self.assertEqual(restored_state["current_segment"], "music_rotation_until_deadline")

    @patch("newsica.broadcast.director_agent.get_current_state")
    @patch("newsica.broadcast.director_agent.write_state_files")
    @patch("newsica.broadcast.director_agent.get_current_block_info")
    @patch("newsica.broadcast.director_agent.schedule_deadline")
    def test_restore_after_interrupt_less_than_40_percent_remaining(self, mock_deadline, mock_block_info, mock_write_state, mock_get_state):
        # Se ora sono le 15:25, mancano solo 5 minuti (< 40%). Dovrebbe passare al prossimo blocco (OFFLINE).
        
        mock_get_state.return_value = {
            "status": "SPECIAL_BROADCAST",
            "interrupted_slot": "15:00",
            "interrupted_block": "sport",
            "interrupted_title": "Leo Sport",
            "next_block": "Meteo",
            "next_start": "15:30"
        }
        
        mock_block_info.return_value = ("sport", "Leo Sport", "Meteo", "15:30", "15:00", 0)
        
        now = datetime.datetime.now()
        mock_deadline.return_value = now + datetime.timedelta(minutes=5)
        
        self.director.handle_restore_after_interrupt()
        
        # Controlla che lo stato sia OFFLINE per forzare il passaggio al prossimo slot
        mock_write_state.assert_called_once_with({"status": "OFFLINE"})

if __name__ == "__main__":
    unittest.main()
