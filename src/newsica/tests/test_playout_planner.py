import os
import unittest
import tempfile
import shutil
from unittest.mock import MagicMock, patch
import datetime

from newsica.broadcast.planner import PlayoutPlanner
from newsica.domain.playout_events import PlayVoiceMixEvent, PlayMusicDeadlineEvent, PlayJingleEvent
from newsica.config.paths import RUNTIME_DIR

class TestPlayoutPlannerMusicOnly(unittest.TestCase):
    def setUp(self):
        self.music_selector = MagicMock(return_value="assets/music/song.mp3")
        self.planner = PlayoutPlanner(self.music_selector)
        
        # Setup temporary RUNTIME_DIR/assets/ready structure
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_runtime_dir = RUNTIME_DIR
        
    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("newsica.broadcast.planner.RUNTIME_DIR")
    def test_plan_block_music_only_no_intro_fallback(self, mock_runtime_dir):
        # Configure temporary runtime directory path
        mock_runtime_dir.joinpath = MagicMock(return_value=self.temp_dir.name)
        
        # Mock paths.RUNTIME_DIR or paths inside it
        with patch("os.path.exists", return_value=False):
            events = self.planner.plan_block(
                block_type="music_only",
                title="Only Music",
                next_time="17:00",
                scheduled_slot="16:00",
                theme="rock"
            )
            
        # Fallback should only contain:
        # 1. Jingle d'apertura
        # 2. PlayMusicDeadlineEvent
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], PlayJingleEvent)
        self.assertIsInstance(events[1], PlayMusicDeadlineEvent)
        self.assertEqual(events[1].label, "music_rotation")

    @patch("newsica.broadcast.planner.RUNTIME_DIR")
    def test_plan_block_music_only_with_intro_success(self, mock_runtime_dir):
        # Configure temporary runtime directory path
        temp_runtime_path = self.temp_dir.name
        
        # We need the relative os.path.join(RUNTIME_DIR, "assets", "ready", "1600") to exist
        ready_dir = os.path.join(temp_runtime_path, "assets", "ready", "1600")
        os.makedirs(ready_dir, exist_ok=True)
        
        voice_file = os.path.join(ready_dir, "audio.wav")
        with open(voice_file, "w") as f:
            f.write("mock audio")
            
        # Mock os.path.exists and other details
        with patch("newsica.broadcast.planner.RUNTIME_DIR", temp_runtime_path):
            events = self.planner.plan_block(
                block_type="music_only",
                title="Only Music",
                next_time="17:00",
                scheduled_slot="16:00",
                theme="rock"
            )
            
        # Should contain:
        # 1. Jingle d'apertura
        # 2. PlayVoiceMixEvent (intro voice)
        # 3. PlayMusicDeadlineEvent (timed loop)
        self.assertEqual(len(events), 3)
        self.assertIsInstance(events[0], PlayJingleEvent)
        self.assertIsInstance(events[1], PlayVoiceMixEvent)
        self.assertIsInstance(events[2], PlayMusicDeadlineEvent)
        
        self.assertEqual(events[1].voice_file, voice_file)
        self.assertEqual(events[1].segment, "intro")
        self.assertEqual(events[1].next_segment, "music_rotation")
        self.assertEqual(events[2].label, "music_rotation")

if __name__ == "__main__":
    unittest.main()
