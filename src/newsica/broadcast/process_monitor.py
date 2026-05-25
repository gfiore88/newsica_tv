import os
import threading
import subprocess

class SubprocessSupervisor:
    def __init__(self, python_exec, base_dir):
        self.python_exec = python_exec
        self.base_dir = base_dir

    def _run_agent(self, script_name):
        subprocess.run([self.python_exec, "-u", os.path.join(self.base_dir, "src", script_name)])

    def _is_agent_running(self, script_name):
        script_path = os.path.join(self.base_dir, "src", script_name)
        try:
            output = subprocess.check_output(
                ["ps", "-Ao", "pid=,command="],
                text=True,
            )
        except Exception:
            return False

        current_pid = os.getpid()
        for line in output.splitlines():
            line = line.strip()
            if not line or script_path not in line:
                continue
            try:
                pid_text, command = line.split(" ", 1)
                pid = int(pid_text)
            except ValueError:
                continue
            if pid == current_pid:
                continue
            if script_path in command:
                return True
        return False

    def start_all(self):
        agents = [
            "preparation_agent.py",
            "ticker_agent.py",
            "overlay_agent.py",
            "hourly_chime_agent.py",
            "chat_agent.py"
        ]
        for agent in agents:
            if self._is_agent_running(agent):
                print(f"ℹ️ [Supervisor] {agent} già attivo, skip avvio duplicato.")
                continue
            threading.Thread(target=self._run_agent, args=(agent,), daemon=True).start()
