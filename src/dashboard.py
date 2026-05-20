from flask import Flask, jsonify, render_template_string, request
import os
import json
import signal
import subprocess
import time
from schedule_generator import get_current_schedule, generate_schedule
from newsica.audio.settings import resolve_ffmpeg_cmd

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
HOUR_CHIME_JINGLE_FILE = os.path.join(BASE_DIR, "assets", "jingles", "jingle_ora_esatta.mp3")
HOUR_CHIME_OUTPUT_FILE = os.path.join(TMP_DIR, "hourly_chime.wav")
HOUR_CHIME_VOICE_FILE = os.path.join(TMP_DIR, "hourly_chime_voice.wav")
FFMPEG_CMD = resolve_ffmpeg_cmd()
PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python3")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = "python3"

SERVICES = {
    "director": {
        "label": "Regia",
        "patterns": [
            r"src/watchdog\.sh",
            r"src/director\.py",
            r"src/ticker_agent\.py",
            r"src/hourly_chime_agent\.py",
            r"src/breaking_news_agent\.py",
        ],
        "command": [PYTHON_EXEC, "-u", os.path.join(BASE_DIR, "src", "director.py")],
        "log": os.path.join(TMP_DIR, "director.log"),
    },
    "stream": {
        "label": "Stream",
        "patterns": [r"src/stream\.sh", r"ffmpeg.*rtmp://a\.rtmp\.youtube\.com/live2"],
        "command": ["bash", os.path.join(BASE_DIR, "src", "stream.sh")],
        "log": os.path.join(TMP_DIR, "stream.log"),
    },
}

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
    <div class="max-w-7xl mx-auto">
        <header class="flex items-center justify-between mb-8 pb-4 border-b border-slate-700">
            <h1 class="text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">NewsicaTV Dashboard</h1>
            <div id="status-badge" class="px-3 py-1 rounded-full text-sm font-bold bg-slate-700 text-slate-300">OFFLINE</div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div class="glass rounded-xl p-6 shadow-xl flex flex-col justify-between">
                <div>
                    <h2 class="text-xs uppercase tracking-widest text-slate-400 font-semibold mb-1">In Onda Ora</h2>
                    <div id="current-title" class="text-2xl font-bold text-white mb-2 truncate">Caricamento...</div>
                </div>
                <div class="flex items-center text-sm text-slate-400 mt-4">
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
                <div class="mt-3 grid grid-cols-2 gap-3">
                    <button onclick="sendCommand('TRIGGER_BREAKING_NEWS')" class="col-span-1 bg-red-600/80 hover:bg-red-500 transition border border-red-500 p-3 rounded-lg font-bold text-sm flex justify-center items-center shadow-[0_0_15px_rgba(239,68,68,0.3)]">
                        🚨 BREAKING NEWS
                    </button>
                    <button id="chime-btn" onclick="triggerChime()" class="col-span-1 bg-amber-600/80 hover:bg-amber-500 transition border border-amber-500 p-3 rounded-lg font-bold text-sm flex justify-center items-center shadow-[0_0_15px_rgba(251,191,36,0.3)]">
                        🔔 Segnale Orario
                    </button>
                </div>
                <div class="mt-5 pt-4 border-t border-slate-700/60">
                    <h3 class="text-xs uppercase tracking-widest text-slate-400 font-semibold mb-3">Servizi</h3>
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <button onclick="restartService('director')" class="bg-amber-700/80 hover:bg-amber-600 transition border border-amber-600 p-3 rounded-lg font-semibold text-sm">
                            ↻ Restart Regia
                        </button>
                        <button onclick="restartService('stream')" class="bg-cyan-700/80 hover:bg-cyan-600 transition border border-cyan-600 p-3 rounded-lg font-semibold text-sm">
                            ↻ Restart Stream
                        </button>
                        <button onclick="restartService('all')" class="bg-purple-700/80 hover:bg-purple-600 transition border border-purple-600 p-3 rounded-lg font-semibold text-sm">
                            ↻ Restart Tutto
                        </button>
                    </div>
                </div>
            </div>

            <!-- Sezione Podcast al Volo -->
            <div class="glass rounded-xl p-6 shadow-xl flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-4 pb-2 border-b border-slate-700/50">
                        <h2 class="text-xs uppercase tracking-widest text-slate-400 font-semibold flex items-center">
                            🎙️ Podcast Talk al Volo
                        </h2>
                        <span class="text-[10px] px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold uppercase tracking-wider">
                            Qwen3-TTS
                        </span>
                    </div>
                    <p class="text-xs text-slate-400 mb-4 leading-relaxed">
                        Digita una tematica (es. <em>il futuro del lavoro</em>). Ollama formulerà il copione e Chiara & Leo condurranno la discussione all'istante.
                    </p>
                    <div class="space-y-3">
                        <textarea id="podcast-topic" rows="3" 
                            class="w-full bg-slate-900/60 border border-slate-700 focus:border-purple-500 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none transition resize-none"
                            placeholder="Inserisci una tematica stimolante per Chiara e Leo..."></textarea>
                    </div>
                </div>
                <div class="mt-4">
                    <button id="podcast-btn" onclick="launchPodcast()" 
                        class="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-sm py-3 px-4 rounded-lg transition-all duration-200 flex justify-center items-center shadow-[0_0_15px_rgba(147,51,234,0.3)]">
                        🚀 Genera e Manda in Onda
                    </button>
                </div>
            </div>
        </div>

        <!-- Sezione Palinsesto di Oggi -->
        <div class="glass rounded-xl p-6 shadow-xl mb-8">
            <div class="flex items-center justify-between mb-6 pb-2 border-b border-slate-700/50">
                <h2 class="text-xs uppercase tracking-widest text-slate-400 font-semibold">📅 Palinsesto di Oggi</h2>
                <span class="text-xs text-slate-500 font-medium hidden sm:inline">Clicca su un blocco per forzarne la messa in onda</span>
            </div>
            <div id="schedule-timeline" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
                <!-- I blocchi verranno inseriti dinamicamente via JS -->
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
                document.getElementById('last-update').innerText = data.last_update ? new Date(data.last_update).toLocaleTimeString() : '--';

                renderSchedule(data.schedule, data.current_title);
            } catch (err) {
                console.error(err);
            }
        }

        function renderSchedule(schedule, currentTitle) {
            const container = document.getElementById('schedule-timeline');
            if (!schedule || schedule.length === 0) {
                container.innerHTML = '<div class="text-slate-500 col-span-full py-4 text-center text-sm">Nessun palinsesto disponibile</div>';
                return;
            }

            const badges = {
                'music_only': { label: '🎵 Musica', color: 'bg-indigo-950/50 text-indigo-300 border-indigo-800/50' },
                'news': { label: '📰 News', color: 'bg-emerald-950/50 text-emerald-300 border-emerald-800/50' },
                'sport': { label: '⚽ Sport', color: 'bg-amber-950/50 text-amber-300 border-amber-800/50' },
                'wellness': { label: '🧘 Benessere', color: 'bg-rose-950/50 text-rose-300 border-rose-800/50' },
                'meteo': { label: '☀️ Meteo', color: 'bg-sky-950/50 text-sky-300 border-sky-800/50' }
            };

            let html = '';
            schedule.forEach(item => {
                const isActive = item.title === currentTitle;
                const activeClasses = isActive 
                    ? 'ring-2 ring-purple-500 bg-gradient-to-br from-slate-800/80 to-indigo-950/80 border-purple-500/50 shadow-[0_0_20px_rgba(147,51,234,0.15)] transform scale-[1.02]' 
                    : 'bg-slate-800/40 hover:bg-slate-800/70 border-slate-700 hover:border-slate-500 transition-all duration-200 cursor-pointer';

                const badge = badges[item.type] || { label: '📦 Altro', color: 'bg-slate-900 text-slate-300' };

                html += `
                    <div onclick="${isActive} ? null : selectBlock(${item.index}, '${item.title}')" class="relative group p-4 rounded-xl border flex flex-col justify-between h-32 ${activeClasses}">
                        ${isActive ? '<span class="absolute -top-1.5 -right-1.5 flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span></span>' : ''}
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-extrabold tracking-wider ${isActive ? 'text-purple-400' : 'text-slate-400'}">${item.time}</span>
                            ${isActive ? '<span class="text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30">IN ONDA</span>' : ''}
                        </div>
                        <div class="text-sm font-semibold truncate ${isActive ? 'text-white' : 'text-slate-200 group-hover:text-white'}">${item.title}</div>
                        <div class="mt-2 flex items-center justify-between">
                            <span class="text-[10px] px-2 py-0.5 rounded-full border ${badge.color}">${badge.label}</span>
                            ${!isActive ? '<span class="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity duration-200 font-semibold flex items-center">Attiva 🚀</span>' : ''}
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }

        async function selectBlock(index, title) {
            if (confirm(`Vuoi forzare la messa in onda immediata del blocco "${title}"?`)) {
                await sendCommand(`FORCE_INDEX_${index}`);
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

        async function restartService(service) {
            const labels = { director: 'regia', stream: 'stream', all: 'regia e stream' };
            if (!confirm(`Riavviare ${labels[service] || service}?`)) {
                return;
            }

            logMsg(`Restart servizio: ${service}`);
            try {
                const res = await fetch('/api/service/restart', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ service })
                });
                const data = await res.json();
                logMsg(`Restart: ${data.status} ${data.message || ''}`);
            } catch (err) {
                logMsg(`Errore restart: ${err}`);
            }
        }

        async function triggerChime() {
            const btn = document.getElementById('chime-btn');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '⏳ Generazione TTS...';
            btn.classList.add('opacity-60');
            logMsg('Generazione segnale orario via TTS...');

            try {
                const res = await fetch('/api/chime', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();
                if (data.status === 'OK') {
                    logMsg(`🔔 Segnale orario inviato: "${data.text}"`);
                    btn.innerHTML = '✅ Inviato!';
                    btn.classList.remove('opacity-60');
                    btn.classList.add('bg-green-600/80', 'border-green-500');
                    setTimeout(() => {
                        btn.innerHTML = originalText;
                        btn.disabled = false;
                        btn.classList.remove('bg-green-600/80', 'border-green-500');
                    }, 3000);
                } else {
                    logMsg(`❌ Errore segnale orario: ${data.message}`);
                    btn.innerHTML = '❌ Errore';
                    setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; btn.classList.remove('opacity-60'); }, 3000);
                }
            } catch (err) {
                logMsg(`❌ Errore fetch: ${err}`);
                btn.innerHTML = originalText;
                btn.disabled = false;
                btn.classList.remove('opacity-60');
            }
        }

        async function launchPodcast() {
            const topicInput = document.getElementById('podcast-topic');
            const topic = topicInput.value.trim();
            if (!topic) {
                alert('Inserisci una descrizione della tematica per il podcast!');
                return;
            }

            const btn = document.getElementById('podcast-btn');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.classList.add('opacity-60');
            
            // Fasi del caricamento animato
            let phase = 0;
            const phases = [
                "🤖 Elaborazione con LLM...",
                "🎙️ Sintesi Chiara (Qwen3)...",
                "🎙️ Sintesi Leo (Qwen3)...",
                "🎛️ Unione dei flussi audio..."
            ];
            
            btn.innerHTML = `⏳ ${phases[0]}`;
            const interval = setInterval(() => {
                phase = (phase + 1) % phases.length;
                btn.innerHTML = `⏳ ${phases[phase]}`;
            }, 6000);

            logMsg(`Richiesta generazione podcast su tematica: "${topic}"`);

            try {
                const res = await fetch('/api/podcast', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic })
                });
                clearInterval(interval);
                
                const data = await res.json();
                if (data.status === 'OK') {
                    logMsg(`🎙️ Podcast in onda: "${data.title}"`);
                    btn.innerHTML = '🚀 Mandato in onda!';
                    btn.classList.remove('opacity-60');
                    btn.classList.add('bg-green-600/80', 'border-green-500');
                    topicInput.value = ''; // svuota l'input
                    setTimeout(() => {
                        btn.innerHTML = originalText;
                        btn.disabled = false;
                        btn.classList.remove('bg-green-600/80', 'border-green-500');
                    }, 3000);
                } else {
                    logMsg(`❌ Errore podcast al volo: ${data.message}`);
                    btn.innerHTML = '❌ Errore';
                    setTimeout(() => { 
                        btn.innerHTML = originalText; 
                        btn.disabled = false; 
                        btn.classList.remove('opacity-60'); 
                    }, 3000);
                }
            } catch (err) {
                clearInterval(interval);
                logMsg(`❌ Errore fetch: ${err}`);
                btn.innerHTML = originalText;
                btn.disabled = false;
                btn.classList.remove('opacity-60');
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
    try:
        schedule_data = get_current_schedule()
        sorted_times = sorted(schedule_data.keys())
        schedule_list = []
        for idx, t in enumerate(sorted_times):
            schedule_list.append({
                "time": t,
                "title": schedule_data[t]["title"],
                "type": schedule_data[t]["type"],
                "index": idx
            })
    except Exception as e:
        print(f"⚠️ Errore caricamento palinsesto: {e}")
        schedule_list = []

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                state = json.load(f)
                state["schedule"] = schedule_list
                return jsonify(state)
            except:
                return jsonify({"status": "ERROR", "schedule": schedule_list})
    return jsonify({"status": "OFFLINE", "schedule": schedule_list})

@app.route('/api/command', methods=['POST'])
def send_command():
    data = request.json
    cmd = data.get('command')
    if cmd:
        with open(CONTROL_FILE, "w") as f:
            f.write(cmd)
        return jsonify({"status": "OK", "command": cmd})
    return jsonify({"status": "INVALID"})


@app.route('/api/chime', methods=['POST'])
def trigger_chime():
    """Genera il segnale orario manuale: jingle + voce con ora reale."""
    import sys

    if not os.path.exists(HOUR_CHIME_JINGLE_FILE):
        return jsonify({
            "status": "ERROR",
            "message": f"Jingle ora esatta non trovato: {HOUR_CHIME_JINGLE_FILE}",
        }), 500

    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    try:
        from hourly_chime_agent import build_exact_chime_text, generate_chime_audio
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Import agente fallito: {e}"}), 500

    text = build_exact_chime_text()
    if not generate_chime_audio(text, HOUR_CHIME_VOICE_FILE):
        return jsonify({"status": "ERROR", "message": "Generazione TTS fallita."}), 500

    try:
        subprocess.run([
            FFMPEG_CMD,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", HOUR_CHIME_JINGLE_FILE,
            "-i", HOUR_CHIME_VOICE_FILE,
            "-filter_complex",
            "[0:a]aresample=24000,aformat=channel_layouts=mono[j];"
            "[1:a]aresample=24000,aformat=channel_layouts=mono[v];"
            "[j][v]concat=n=2:v=0:a=1[a]",
            "-map", "[a]",
            "-ar", "24000",
            "-ac", "1",
            HOUR_CHIME_OUTPUT_FILE,
        ], check=True)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Preparazione jingle ora esatta fallita: {e}"}), 500

    cmd = f"HOURLY_CHIME_READY|{HOUR_CHIME_OUTPUT_FILE}|force"
    try:
        with open(CONTROL_FILE, "w") as f:
            f.write(cmd)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Scrittura controllo fallita: {e}"}), 500

    return jsonify({"status": "OK", "text": text})

@app.route('/api/podcast', methods=['POST'])
def trigger_podcast():
    """Genera il copione del podcast via Ollama, lo sintetizza via Qwen3-TTS e lo manda in onda."""
    data = request.json or {}
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"status": "ERROR", "message": "Nessuna tematica fornita."}), 400

    # 1. Carica il prompt di sistema
    prompt_path = os.path.join(BASE_DIR, "src", "newsica", "editorial", "prompts", "podcast.md")
    system_prompt = ""
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as pf:
                system_prompt = pf.read()
        except Exception as e:
            print(f"⚠️ Impossibile leggere il prompt del podcast: {e}")
    
    if not system_prompt:
        system_prompt = "Sei un duo di conduttori radiofonici e podcaster professionisti di NewsicaTV. Genera un copione per una rubrica stile podcast in formato dialogo a due voci Giulia e Marco."

    # 2. Prepara il prompt per Ollama
    user_prompt = f"Scrivi un copione per il podcast 'Newsica Talk' sulla seguente tematica descritta dall'utente:\n\n\"{topic}\"\n\nRispetta rigorosamente eventuali indicazioni di durata o brevità fornite dall'utente nella tematica. Se non specificato, sviluppa un dialogo naturale e ricco di circa 250-350 parole. Il dialogo deve essere diviso a turni di parola tra Giulia e Marco usando esattamente i tag [SPEAKER: Giulia] e [SPEAKER: Marco] all'inizio di ogni battuta."

    # 3. Interroga Ollama locale
    import requests
    ollama_url = "http://localhost:11434/api/generate"
    model_name = os.getenv("OLLAMA_MODEL", "gemma3:12b")
    
    payload = {
        "model": model_name,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.5,
            "num_predict": 600,
        },
    }

    script_text = ""
    try:
        response = requests.post(ollama_url, json=payload, timeout=60)
        response.raise_for_status()
        script_text = response.json().get("response", "").strip()
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Errore di connessione a Ollama: {e}"}), 500

    if not script_text:
        return jsonify({"status": "ERROR", "message": "Ollama ha restituito un copione vuoto."}), 500

    # 4. Scrivi il copione in tmp/script.txt
    script_file = os.path.join(TMP_DIR, "script.txt")
    try:
        with open(script_file, "w", encoding="utf-8") as sf:
            sf.write(script_text)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Scrittura copione fallita: {e}"}), 500

    # 5. Genera l'audio via tts_generator.py podcast
    try:
        subprocess.run(
            [PYTHON_EXEC, os.path.join(BASE_DIR, "src", "tts_generator.py"), "podcast"],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        return jsonify({
            "status": "ERROR", 
            "message": "Sintesi audio fallita.", 
            "details": e.stderr
        }), 500

    podcast_audio_file = os.path.join(TMP_DIR, "audio.wav")
    if not os.path.exists(podcast_audio_file):
        return jsonify({"status": "ERROR", "message": "Audio del podcast non trovato dopo la sintesi."}), 500

    # 6. Estrai una versione corta del titolo
    short_title = topic[:30] + "..." if len(topic) > 30 else topic
    pod_display_title = f"Talk: {short_title}"

    # 7. Invia comando alla regia
    cmd = f"PLAY_PODCAST_IMMEDIATE|{podcast_audio_file}|{pod_display_title}"
    try:
        with open(CONTROL_FILE, "w") as f:
            f.write(cmd)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Scrittura comando regia fallita: {e}"}), 500

    return jsonify({"status": "OK", "title": pod_display_title})

def find_pids(patterns):
    pids = set()
    for pattern in patterns:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid != os.getpid():
                pids.add(pid)
    return sorted(pids)

def terminate_pids(pids):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    deadline = time.time() + 5
    while time.time() < deadline:
        if not any(process_exists(pid) for pid in pids):
            return
        time.sleep(0.2)

    for pid in pids:
        if process_exists(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

def process_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

def start_service(service):
    os.makedirs(TMP_DIR, exist_ok=True)
    log_file = open(service["log"], "a")
    subprocess.Popen(
        service["command"],
        cwd=BASE_DIR,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )

def restart_service(name):
    service = SERVICES[name]
    pids = find_pids(service["patterns"])
    terminate_pids(pids)
    start_service(service)
    return pids

@app.route('/api/service/restart', methods=['POST'])
def restart_service_route():
    data = request.json or {}
    requested_service = data.get("service")

    if requested_service == "all":
        restarted = {}
        for service_name in ("director", "stream"):
            restarted[service_name] = restart_service(service_name)
        return jsonify({
            "status": "OK",
            "message": "servizi riavviati",
            "restarted": restarted,
        })

    if requested_service not in SERVICES:
        return jsonify({"status": "INVALID", "message": "servizio non valido"}), 400

    pids = restart_service(requested_service)
    return jsonify({
        "status": "OK",
        "message": f"{SERVICES[requested_service]['label']} riavviato",
        "restarted_pids": pids,
    })

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
