import json
import os

from flask import jsonify

from newsica.audio.music_library import DEFAULT_RECENT_WINDOW
from newsica.storage.database import get_connection
from newsica.storage.repositories.audio_metadata_repository import get_metadata


def _format_memory_value(raw_value):
    if raw_value is None:
        return {"text": "", "is_json": False, "summary": ""}
    if not isinstance(raw_value, str):
        raw_value = str(raw_value)
    trimmed = raw_value.strip()
    if not trimmed:
        return {"text": "", "is_json": False, "summary": ""}
    try:
        parsed = json.loads(trimmed)
    except Exception:
        return {"text": raw_value, "is_json": False, "summary": ""}

    summary = ""
    if isinstance(parsed, dict):
        interesting_keys = [
            key for key in (
                "status",
                "current_title",
                "current_block",
                "next_block",
                "author",
                "message",
                "mode",
                "theme",
                "requested_by",
                "requested_title",
            )
            if parsed.get(key)
        ]
        summary = " | ".join(f"{key}: {parsed[key]}" for key in interesting_keys[:4])
    elif isinstance(parsed, list):
        summary = f"{len(parsed)} elementi"

    return {
        "text": json.dumps(parsed, ensure_ascii=False, indent=2),
        "is_json": True,
        "summary": summary,
    }


def _resolve_track_display_title(asset_path):
    if not asset_path:
        return ""

    try:
        meta_row = get_metadata(os.path.realpath(asset_path))
    except Exception:
        meta_row = None

    if meta_row:
        artist = " ".join(str(meta_row.get("artist", "")).split())
        title = " ".join(str(meta_row.get("title", "")).split())
        if artist and title:
            return f"{artist} - {title}"
        if title:
            return title
        metadata = meta_row.get("metadata") or {}
        meta_title = " ".join(str(metadata.get("title", "")).split())
        if meta_title:
            return meta_title

    root, ext = os.path.splitext(asset_path)
    if ext.lower() in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}:
        sidecar_path = root + ".meta"
        if os.path.exists(sidecar_path):
            try:
                with open(sidecar_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                sidecar_title = " ".join(str(payload.get("title", "")).split())
                if sidecar_title:
                    return sidecar_title
            except Exception:
                pass

    fallback_title = os.path.splitext(os.path.basename(asset_path))[0].replace("_", " ").strip()
    return " ".join(fallback_title.split())


def _decorate_history_row(row):
    item = dict(row)
    item["display_title"] = item.get("title") or "--"
    item["display_detail"] = item.get("segment") or item.get("block_type") or "--"

    if item.get("block_type") == "music":
        track_title = _resolve_track_display_title(item.get("asset_path"))
        if track_title:
            item["display_title"] = track_title
        label = item.get("title") or ""
        if label and label not in {"music_rotation", "fallback_non_pronto"}:
            item["display_detail"] = label
        elif item.get("segment"):
            item["display_detail"] = item["segment"]

    return item


def _load_rotation_runtime(runtime_dir):
    history_path = os.path.join(runtime_dir, "music_rotation_history.json")
    blocks_path = os.path.join(runtime_dir, "music_rotation_blocks.json")

    try:
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                history_payload = json.load(f)
        else:
            history_payload = {}
    except Exception:
        history_payload = {}

    try:
        if os.path.exists(blocks_path):
            with open(blocks_path, "r", encoding="utf-8") as f:
                blocks_payload = json.load(f)
        else:
            blocks_payload = {}
    except Exception:
        blocks_payload = {}

    recent_tracks = []
    for track_path in history_payload.get("recent_tracks", []):
        resolved = os.path.realpath(track_path)
        recent_tracks.append({
            "path": resolved,
            "display_title": _resolve_track_display_title(resolved),
            "filename": os.path.basename(resolved),
        })

    block_events = []
    for entry in reversed(blocks_payload.get("events", [])):
        blocked_tracks = []
        for track_path in entry.get("blocked_tracks", []):
            resolved = os.path.realpath(track_path)
            if not os.path.exists(resolved):
                continue
            blocked_tracks.append({
                "path": resolved,
                "display_title": _resolve_track_display_title(resolved),
                "filename": os.path.basename(resolved),
            })
        if not blocked_tracks:
            continue
        block_events.append({
            "timestamp": entry.get("timestamp"),
            "reason": entry.get("reason", "recent_window"),
            "recent_window": entry.get("recent_window", 0),
            "candidate_count": entry.get("candidate_count", 0),
            "blocked_count": len(blocked_tracks),
            "blocked_tracks": blocked_tracks,
        })

    return {
        "configured_window": DEFAULT_RECENT_WINDOW,
        "tracked_count": len(recent_tracks),
        "recent_tracks": recent_tracks,
        "block_events": block_events,
    }


def register_history_routes(app, *, runtime_dir):
    @app.route('/api/db/history', methods=['GET'])
    def get_db_history():
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM broadcast_history
                    ORDER BY id DESC LIMIT 50
                ''')
                rows = [_decorate_history_row(row) for row in cursor.fetchall()]
            return jsonify({"status": "OK", "data": rows})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)})

    @app.route('/api/db/memory', methods=['GET'])
    def get_db_memory():
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM editorial_memory
                    ORDER BY id DESC LIMIT 50
                ''')
                rows = []
                for row in cursor.fetchall():
                    item = dict(row)
                    formatted = _format_memory_value(item.get("value"))
                    item["value_pretty"] = formatted["text"]
                    item["value_is_json"] = formatted["is_json"]
                    item["value_summary"] = formatted["summary"]
                    rows.append(item)
            return jsonify({"status": "OK", "data": rows})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)})

    @app.route('/api/db/assets', methods=['GET'])
    def get_db_assets():
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM asset_slots
                    ORDER BY slot_time ASC LIMIT 50
                ''')
                rows = [dict(row) for row in cursor.fetchall()]
            return jsonify({"status": "OK", "data": rows})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)})

    @app.route('/api/db/music-rotation', methods=['GET'])
    def get_music_rotation_debug():
        try:
            return jsonify({"status": "OK", "data": _load_rotation_runtime(runtime_dir)})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)})

    @app.route('/api/db/generation-jobs', methods=['GET'])
    def get_db_generation_jobs():
        from flask import request as flask_request
        try:
            status_filter = flask_request.args.get('status', '').strip() or None
            limit = min(int(flask_request.args.get('limit', 200)), 500)
            with get_connection() as conn:
                if status_filter and status_filter != 'all':
                    rows = conn.execute(
                        "SELECT * FROM generation_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                        (status_filter, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM generation_jobs ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            jobs = []
            for row in rows:
                item = dict(row)
                # Calcola durata in secondi se started_at e ended_at sono disponibili
                try:
                    import datetime as _dt
                    s = item.get("started_at")
                    e = item.get("ended_at")
                    if s and e:
                        start = _dt.datetime.fromisoformat(s)
                        end = _dt.datetime.fromisoformat(e)
                        item["duration_seconds"] = round((end - start).total_seconds(), 1)
                    else:
                        item["duration_seconds"] = None
                except Exception:
                    item["duration_seconds"] = None
                # Rimuovi campi pesanti non necessari per la lista
                item.pop("payload_json", None)
                item.pop("artifact_manifest_json", None)
                jobs.append(item)
            return jsonify({"status": "OK", "data": jobs})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)})

