import os
import threading
import subprocess

class SubprocessSupervisor:
    def __init__(self, python_exec, base_dir):
        self.python_exec = python_exec
        self.base_dir = base_dir

    def _run_agent(self, script_name):
        subprocess.run([self.python_exec, "-u", os.path.join(self.base_dir, "src", script_name)])

    def start_all(self):
        agents = [
            "preparation_agent.py",
            "ticker_agent.py",
            "overlay_agent.py",
            "hourly_chime_agent.py",
            "chat_agent.py"
        ]
        for agent in agents:
            threading.Thread(target=self._run_agent, args=(agent,), daemon=True).start()
