from flask import Flask, send_from_directory
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env prima di qualsiasi altro modulo
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_base_dir, ".env"))

from newsica.audio.ai_music_runtime import resolve_ace_step_python
from newsica.audio.settings import resolve_ffmpeg_cmd
from newsica.web.control_routes import register_control_routes
from newsica.web.editorial_routes import register_editorial_routes
from newsica.web.history_routes import register_history_routes
from newsica.web.system_routes import register_system_routes
from newsica.shorts.daily_planner import DailyShortsPlanner
from newsica.web.shorts_routes import register_shorts_routes
from newsica.web.sources_routes import register_sources_routes


app = Flask(__name__)
shorts_daily_planner = DailyShortsPlanner()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
HOUR_CHIME_JINGLE_FILE = os.path.join(BASE_DIR, "assets", "jingles", "jingle_ora_esatta.mp3")
HOUR_CHIME_OUTPUT_FILE = os.path.join(TMP_DIR, "hourly_chime.wav")
HOUR_CHIME_VOICE_FILE = os.path.join(TMP_DIR, "hourly_chime_voice.wav")
FFMPEG_CMD = resolve_ffmpeg_cmd()
ACE_STEP_PYTHON = resolve_ace_step_python()
PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python3")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = "python3"

register_shorts_routes(app, base_dir=BASE_DIR, shorts_daily_planner=shorts_daily_planner)
register_history_routes(app, runtime_dir=RUNTIME_DIR)
register_control_routes(app, control_file=CONTROL_FILE, runtime_dir=RUNTIME_DIR)
register_sources_routes(app)

SERVICES = {
    "director": {
        "label": "Regia",
        "patterns": [
            r"src/watchdog\.sh",
            r"src/director\.py",
            r"src/ticker_agent\.py",
            r"src/overlay_agent\.py",
            r"src/hourly_chime_agent\.py",
            r"src/breaking_news_agent\.py",
            r"src/chat_agent\.py",
        ],
        "command": ["bash", os.path.join(BASE_DIR, "src", "watchdog.sh")],
        "log": os.path.join(TMP_DIR, "director.log"),
    },
    "stream": {
        "label": "Stream",
        "patterns": [r"src/stream\.sh", r"ffmpeg.*rtmp://a\.rtmp\.youtube\.com/live2"],
        "command": ["bash", os.path.join(BASE_DIR, "src", "stream.sh")],
        "log": os.path.join(TMP_DIR, "stream.log"),
    },
    "chat_agent": {
        "label": "YouTube Chat",
        "patterns": [r"src/chat_agent\.py"],
        "command": [PYTHON_EXEC, "-u", os.path.join(BASE_DIR, "src", "chat_agent.py")],
        "log": os.path.join(TMP_DIR, "chat_agent.log"),
    },
    "ai_music_worker": {
        "label": "Musica AI Worker",
        "patterns": [r"src/newsica/audio/ai_music_worker\.py"],
        "command": [ACE_STEP_PYTHON, "-u", os.path.join(BASE_DIR, "src", "newsica", "audio", "ai_music_worker.py")],
        "log": os.path.join(TMP_DIR, "ai_music_worker.log"),
    },
    "telegram_agent": {
        "label": "Telegram Bot",
        "patterns": [r"src/telegram_agent\.py"],
        "command": [PYTHON_EXEC, "-u", os.path.join(BASE_DIR, "src", "telegram_agent.py")],
        "log": os.path.join(TMP_DIR, "telegram_agent.log"),
    },
}

register_system_routes(
    app,
    base_dir=BASE_DIR,
    tmp_dir=TMP_DIR,
    services=SERVICES,
    ace_step_python=ACE_STEP_PYTHON,
)

register_editorial_routes(
    app,
    base_dir=BASE_DIR,
    tmp_dir=TMP_DIR,
    control_file=CONTROL_FILE,
    ffmpeg_cmd=FFMPEG_CMD,
    python_exec=PYTHON_EXEC,
    hour_chime_jingle_file=HOUR_CHIME_JINGLE_FILE,
    hour_chime_output_file=HOUR_CHIME_OUTPUT_FILE,
    hour_chime_voice_file=HOUR_CHIME_VOICE_FILE,
)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    asset_path = os.path.join(FRONTEND_DIST_DIR, path)
    if path and os.path.exists(asset_path) and os.path.isfile(asset_path):
        return send_from_directory(FRONTEND_DIST_DIR, path)
    return send_from_directory(FRONTEND_DIST_DIR, 'index.html')

_singleton_lock = None

def check_singleton(name):
    import fcntl
    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")
    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        global _singleton_lock
        _singleton_lock = f
        f.write(str(os.getpid()))
        f.flush()
        return True
    except (IOError, OSError):
        print(f"❌ ERRORE: Un'altra istanza di {name} è già in esecuzione!")
        return False

if __name__ == '__main__':
    import sys
    if not check_singleton("dashboard"):
        print("❌ Uscita immediata per prevenire conflitti.")
        sys.exit(1)
        
    print("🚀 Web Dashboard avviata su http://0.0.0.0:5050")
    app.run(host='0.0.0.0', port=5050, debug=False)
