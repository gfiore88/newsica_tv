import unittest
from unittest.mock import Mock, patch

import director


class DirectorShutdownTest(unittest.TestCase):
    def setUp(self):
        director.shutdown_requested.clear()
        director.schedule_interrupt_event.clear()
        director.fifo_connected_event.clear()

    def tearDown(self):
        director.shutdown_requested.clear()
        director.schedule_interrupt_event.clear()
        director.fifo_connected_event.clear()

    def test_request_shutdown_stops_audio_and_unblocks_waiters(self):
        fake_playout = Mock()
        with patch.object(director, "playout", fake_playout):
            director.request_shutdown("test shutdown", force_exit=False)

        self.assertTrue(director.shutdown_requested.is_set())
        self.assertTrue(director.schedule_interrupt_event.is_set())
        self.assertTrue(director.fifo_connected_event.is_set())
        fake_playout.stop_current_process.assert_called_once_with(
            "🛑 Arresto audio corrente per shutdown del director."
        )
        fake_playout.clear_queue.assert_called_once_with()

    def test_wait_for_fifo_connection_returns_true_when_connected(self):
        director.fifo_connected_event.set()

        self.assertTrue(director.wait_for_fifo_connection(poll_interval=0.01))

    def test_wait_for_fifo_connection_returns_false_when_shutdown_requested(self):
        director.shutdown_requested.set()

        self.assertFalse(director.wait_for_fifo_connection(poll_interval=0.01))


if __name__ == "__main__":
    unittest.main()
