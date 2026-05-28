import os

from flask import jsonify, request

from newsica.audio.music_library import MusicLibrary
from newsica.audio.music_mode import (
    MUSIC_MODE_AI_ONLY,
    MUSIC_MODE_MIXED,
    read_music_mode,
    write_music_mode,
)
from schedule_generator import get_current_schedule


def _music_mode_payload(status="OK", warning=None):
    mode = read_music_mode()
    counts = MusicLibrary().get_counts()
    label = "Solo Musica AI" if mode == MUSIC_MODE_AI_ONLY else "Mix cartella music + Musica AI"
    payload = {
        "status": status,
        "mode": mode,
        "label": label,
        "counts": counts,
    }
    if warning:
        payload["warning"] = warning
    return payload


def register_control_routes(app, *, control_file, runtime_dir):
    @app.route('/api/state')
    def get_state():
        try:
            schedule_data = get_current_schedule()
            sorted_times = sorted(schedule_data.keys())
            schedule_list = []
            for idx, slot_time in enumerate(sorted_times):
                schedule_list.append({
                    "time": slot_time,
                    "title": schedule_data[slot_time]["title"],
                    "type": schedule_data[slot_time]["type"],
                    "index": idx
                })
        except Exception as e:
            print(f"⚠️ Errore caricamento palinsesto: {e}")
            schedule_list = []

        from newsica.broadcast.runtime_state import get_current_state
        state = get_current_state()
        state["schedule"] = schedule_list
        return jsonify(state)

    @app.route('/api/command', methods=['POST'])
    def send_command():
        data = request.json or {}
        cmd = data.get('command')
        if cmd:
            with open(control_file, "w", encoding="utf-8") as f:
                f.write(cmd)
            return jsonify({"status": "OK", "command": cmd})
        return jsonify({"status": "INVALID"})

    @app.route("/api/music_mode", methods=["GET", "POST"])
    def api_music_mode():
        if request.method == "POST":
            data = request.json or {}
            mode = data.get("mode")
            if mode not in {MUSIC_MODE_MIXED, MUSIC_MODE_AI_ONLY}:
                return jsonify({
                    "status": "ERROR",
                    "message": "Modalità non valida. Usa 'mixed' oppure 'ai_only'.",
                }), 400

            write_music_mode(mode)
            counts = MusicLibrary().get_counts()
            warning = None
            if mode == MUSIC_MODE_AI_ONLY and counts.get("ai", 0) == 0:
                warning = "Modalità solo AI attiva, ma assets/ai_music non contiene brani riproducibili."
            return jsonify(_music_mode_payload(warning=warning))

        return jsonify(_music_mode_payload())

    @app.route("/api/audit-log", methods=["GET"])
    def api_audit_log():
        audit_file = os.path.join(runtime_dir, "audit_trail.log")
        try:
            if not os.path.exists(audit_file):
                return jsonify({"lines": ["L'Audit Log è attualmente vuoto o in attesa di dati..."]})

            with open(audit_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            recent_lines = [line.strip() for line in lines[-100:] if line.strip()]
            return jsonify({"lines": list(reversed(recent_lines))})
        except Exception as e:
            return jsonify({"lines": [f"Errore caricamento log: {str(e)}"]})
