import unittest
from unittest.mock import MagicMock, patch

from newsica.broadcast.process_monitor import SubprocessSupervisor


class TestProcessMonitor(unittest.TestCase):
    def setUp(self):
        self.supervisor = SubprocessSupervisor("/tmp/python3", "/project")

    @patch("newsica.broadcast.process_monitor.subprocess.check_output")
    @patch("newsica.broadcast.process_monitor.os.getpid", return_value=1234)
    def test_is_agent_running_detects_other_process(self, _mock_pid, mock_check_output):
        mock_check_output.return_value = (
            "1234 /tmp/python3 -u /project/src/director.py\n"
            "5678 /tmp/python3 -u /project/src/ticker_agent.py\n"
        )

        self.assertTrue(self.supervisor._is_agent_running("ticker_agent.py"))

    @patch("newsica.broadcast.process_monitor.subprocess.check_output")
    @patch("newsica.broadcast.process_monitor.os.getpid", return_value=5678)
    def test_is_agent_running_ignores_current_process(self, _mock_pid, mock_check_output):
        mock_check_output.return_value = "5678 /tmp/python3 -u /project/src/ticker_agent.py\n"

        self.assertFalse(self.supervisor._is_agent_running("ticker_agent.py"))

    @patch("newsica.broadcast.process_monitor.threading.Thread")
    @patch.object(SubprocessSupervisor, "_is_agent_running")
    def test_start_all_skips_already_running_agents(self, mock_is_running, mock_thread):
        mock_is_running.side_effect = lambda script: script in {"ticker_agent.py", "chat_agent.py"}

        self.supervisor.start_all()

        started_agents = [
            call.kwargs["args"][0]
            for call in mock_thread.call_args_list
        ]
        self.assertNotIn("ticker_agent.py", started_agents)
        self.assertNotIn("chat_agent.py", started_agents)
        self.assertIn("preparation_agent.py", started_agents)
        self.assertIn("overlay_agent.py", started_agents)


if __name__ == "__main__":
    unittest.main()
