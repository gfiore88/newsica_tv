import os
from datetime import datetime

from flask import jsonify, request, send_from_directory

from newsica.shorts.api_service import (
    delete_shorts_payload,
    generate_short_payload,
    list_shorts_payload,
    publish_short_payload,
)
from newsica.shorts.plan_executor import process_one_planned_short_item
from newsica.storage.repositories.shorts_plan_repository import (
    get_daily_plan,
    list_plan_items,
    summarize_plan_status,
)


def register_shorts_routes(app, *, base_dir, shorts_daily_planner):
    @app.route('/api/generate_short', methods=['POST'])
    def generate_short():
        data = request.json or {}
        payload, code = generate_short_payload(data.get("mode", "news"))
        return jsonify(payload), code

    @app.route('/api/shorts_publish', methods=['POST'])
    def shorts_publish():
        data = request.json or {}
        payload, code = publish_short_payload(base_dir, data.get("filename"), data.get("platform"))
        return jsonify(payload), code

    @app.route('/api/shorts_plan_today', methods=['GET'])
    def shorts_plan_today():
        target_date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
        day = get_daily_plan(target_date)
        items = list_plan_items(target_date)
        summary = summarize_plan_status(target_date)
        return jsonify({
            "date": target_date,
            "plan": day or {},
            "summary": summary,
            "items": items,
        })

    @app.route('/api/shorts_plan_rebuild', methods=['POST'])
    def shorts_plan_rebuild():
        data = request.json or {}
        force = bool(data.get("force", True))
        result = shorts_daily_planner.reconcile_today_plan(force=force)
        code = 200 if result.get("status") in {"planned", "existing", "disabled"} else 500
        return jsonify(result), code

    @app.route('/api/shorts_plan_process_once', methods=['POST'])
    def shorts_plan_process_once():
        result = process_one_planned_short_item()
        code = 200 if result.get("status") in {"success", "partial", "idle"} else 500
        return jsonify(result), code

    @app.route('/api/shorts_library', methods=['GET'])
    def shorts_library():
        return jsonify(list_shorts_payload(base_dir))

    @app.route('/api/shorts_video/<path:filename>')
    def serve_short_video(filename):
        shorts_dir = os.path.join(base_dir, "output", "shorts")
        return send_from_directory(shorts_dir, filename)

    @app.route('/api/shorts_delete', methods=['POST'])
    def shorts_delete():
        data = request.json or {}
        payload, code = delete_shorts_payload(base_dir, data.get("filenames") or [])
        return jsonify(payload), code
