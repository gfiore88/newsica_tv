import os
import tempfile
import unittest

from newsica.broadcast.control_bus import poll_control_file


class TestControlBus(unittest.TestCase):
    def test_parse_play_event_immediate_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            control_file = os.path.join(tmpdir, "control.txt")
            with open(control_file, "w", encoding="utf-8") as handle:
                handle.write("PLAY_EVENT_IMMEDIATE|/tmp/audio.wav|Flash 60 Secondi|flash_60s")

            command = poll_control_file(control_file)

            self.assertIsNotNone(command)
            self.assertEqual(command.name, "PLAY_EVENT_IMMEDIATE")
            self.assertEqual(command.kwargs["event_file"], "/tmp/audio.wav")
            self.assertEqual(command.kwargs["event_title"], "Flash 60 Secondi")
            self.assertEqual(command.kwargs["character_id"], "flash_60s")


if __name__ == "__main__":
    unittest.main()
