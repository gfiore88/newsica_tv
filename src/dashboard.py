from flask import Flask, jsonify, render_template_string, request
import os
import json

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NewsicaTV - Regia</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; }
        .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .pulse { animation: pulse-red 2s infinite; }
        @keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); } 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } }
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="max-w-4xl mx-auto">
        <header class="flex items-center justify-between mb-8 pb-4 border-b border-slate-700">
            <h1 class="text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">NewsicaTV Dashboard</h1>
            <div id="status-badge" class="px-3 py-1 rounded-full text-sm font-bold bg-slate-700 text-slate-300">OFFLINE</div>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="glass rounded-xl p-6 shadow-xl">
                <h2 class="text-xs uppercase tracking-widest text-slate-400 font-semibold mb-1">In Onda Ora</h2>
                <div id="current-title" class="text-2xl font-bold text-white mb-2 truncate">Caricamento...</div>
                <div class="flex items-center text-sm text-slate-400 mb-4">
                    <span id="current-block" class="px-2 py-0.5 rounded bg-blue-900/50 text-blue-300 mr-2 border border-blue-800">--</span>
                    Aggiornato: <span id="last-update" class="ml-1">--</span>
                </div>
            </div>

            <div class="glass rounded-xl p-6 shadow-xl flex flex-col justify-center">
                <h2 class="text-xs uppercase tracking-widest text-slate-400 font-semibold mb-4">Controlli di Regia</h2>
                <div class="flex flex-wrap gap-3">
                    <button onclick="sendCommand('FORCE_NEXT')" class="flex-1 bg-slate-700 hover:bg-slate-600 transition p-3 rounded-lg font-semibold text-sm flex justify-center items-center">
                        ⏭️ Salta Blocco
                    </button>
                    <button onclick="sendCommand('REGEN_SCHEDULE')" class="flex-1 bg-slate-700 hover:bg-slate-600 transition p-3 rounded-lg font-semibold text-sm flex justify-center items-center">
                        📅 Rigenera Palinsesto
                    </button>
                </div>
                <div class="mt-3">
                    <button onclick="sendCommand('TRIGGER_BREAKING_NEWS')" class="w-full bg-red-600/80 hover:bg-red-500 transition border border-red-500 p-3 rounded-lg font-bold text-sm flex justify-center items-center shadow-[0_0_15px_rgba(239,68,68,0.3)]">
                        🚨 FORZA BREAKING NEWS
                    </button>
                </div>
            </div>
        </div>
        
        <div class="glass rounded-xl p-6 shadow-xl">
            <h2 class="text-xs uppercase tracking-widest text-slate-400 font-semibold mb-4">Log di Sistema</h2>
            <div id="action-log" class="font-mono text-xs text-green-400 h-32 overflow-y-auto bg-black/50 p-4 rounded border border-slate-700">
                Sistema inizializzato...<br>
            </div>
        </div>
    </div>

    <script>
        function logMsg(msg) {
            const logPanel = document.getElementById('action-log');
            const time = new Date().toLocaleTimeString();
            logPanel.innerHTML += `[${time}] ${msg}<br>`;
            logPanel.scrollTop = logPanel.scrollHeight;
        }

        async function fetchState() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                
                const badge = document.getElementById('status-badge');
                if (data.status === 'ON_AIR') {
                    badge.className = 'pulse px-3 py-1 rounded-full text-sm font-bold bg-red-500 text-white shadow-[0_0_10px_rgba(239,68,68,0.5)]';
                    badge.innerText = 'ON AIR';
                } else {
                    badge.className = 'px-3 py-1 rounded-full text-sm font-bold bg-slate-700 text-slate-300';
                    badge.innerText = 'OFFLINE';
                }

                document.getElementById('current-title').innerText = data.current_title || '--';
                document.getElementById('current-block').innerText = data.current_block || '--';
                document.getElementById('last-update').innerText = data.last_update || '--';
            } catch (err) {
                console.error(err);
            }
        }

        async function sendCommand(cmd) {
            logMsg(`Invio comando: ${cmd}`);
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                const data = await res.json();
                logMsg(`Risposta: ${data.status}`);
            } catch (err) {
                logMsg(`Errore comando: ${err}`);
            }
        }

        setInterval(fetchState, 2000);
        fetchState();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/state')
def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                return jsonify(json.load(f))
            except:
                return jsonify({"status": "ERROR"})
    return jsonify({"status": "OFFLINE"})

@app.route('/api/command', methods=['POST'])
def send_command():
    data = request.json
    cmd = data.get('command')
    if cmd:
        with open(CONTROL_FILE, "w") as f:
            f.write(cmd)
        return jsonify({"status": "OK", "command": cmd})
    return jsonify({"status": "INVALID"})

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
