import os
import random
import re
from datetime import datetime

from flask import jsonify, request, send_from_directory

from newsica.shorts.metadata_reader import read_short_metadata
from newsica.shorts.plan_executor import process_one_planned_short_item
from newsica.storage.repositories.shorts_library_repository import delete_shorts, mark_short_social_posts
from newsica.storage.repositories.shorts_plan_repository import (
    get_daily_plan,
    list_plan_items,
    summarize_plan_status,
)


def register_shorts_routes(app, *, base_dir, shorts_daily_planner):
    @app.route('/api/generate_short', methods=['POST'])
    def generate_short():
        data = request.json or {}
        mode = str(data.get("mode", "news")).strip().lower() or "news"
        if mode == "random":
            mode = random.choice(["news", "breaking", "sport", "meteo", "tech", "wellness", "funfact"])
        if mode not in {"news", "breaking", "sport", "meteo", "tech", "wellness", "funfact"}:
            return jsonify({"status": "error", "message": "Modalità short non valida."}), 400
        try:
            from newsica.agents.shorts_agent import ShortsAgent

            agent = ShortsAgent()
            result = agent.run(mode=mode)
            if result.get("status") == "success":
                output_file = result.get("output", "")
                filename = os.path.basename(output_file) if output_file else ""
                result["filename"] = filename
                result["video_url"] = f"/api/shorts_video/{filename}" if filename else ""
                return jsonify(result), 200
            return jsonify(result), 500
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/shorts_publish', methods=['POST'])
    def shorts_publish():
        data = request.json or {}
        filename = data.get("filename")
        platform = data.get("platform")  # 'youtube', 'instagram', 'tiktok', 'all'

        if not filename or not platform:
            return jsonify({"status": "error", "message": "Parametri mancanti."}), 400

        shorts_dir = os.path.join(base_dir, "output", "shorts")
        video_path = os.path.join(shorts_dir, filename)

        if not os.path.exists(video_path):
            return jsonify({"status": "error", "message": "File video non trovato."}), 404

        metadata = read_short_metadata(video_path)
        title = metadata.get("news_title", "Short NewsicaTV")
        caption = metadata.get("caption", "")
        hashtags = metadata.get("hashtags_text", "")
        full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption

        from newsica.utils.social_publisher import SocialPublisher

        publisher = SocialPublisher()

        if platform == "youtube":
            res = publisher.publish_to_youtube(video_path, title, full_caption)
        elif platform == "instagram":
            res = publisher.publish_to_instagram(video_path, full_caption)
        elif platform == "tiktok":
            res = publisher.publish_to_tiktok(video_path, title, full_caption)
        elif platform == "all":
            res = publisher.publish_to_all_socials(video_path, title, full_caption)
        else:
            return jsonify({"status": "error", "message": "Piattaforma non supportata."}), 400

        platform_results = res.get("results")
        if not isinstance(platform_results, dict):
            platform_results = {platform: res}
        social_posts = mark_short_social_posts(filename, platform_results)

        if res.get("status") == "success":
            return jsonify({"status": "OK", "message": res.get("message"), "social_posts": social_posts}), 200
        if res.get("status") == "partial":
            return jsonify({"status": "partial", "message": res.get("message"), "results": res.get("results", {}), "social_posts": social_posts}), 200
        return jsonify({"status": res.get("status", "config_missing"), "message": res.get("message"), "results": res.get("results", {}), "social_posts": social_posts}), 200

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
        import glob

        shorts_dir = os.path.join(base_dir, "output", "shorts")
        if not os.path.exists(shorts_dir):
            return jsonify({"shorts": []})

        shorts = []
        for filepath in glob.glob(os.path.join(shorts_dir, "*.mp4")):
            filename = os.path.basename(filepath)

            match = re.search(r'short_(\d{8})_(\d{6})', filename)
            if match:
                date_str = match.group(1)
                time_str = match.group(2)
                try:
                    dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                except Exception:
                    dt = datetime.fromtimestamp(os.path.getmtime(filepath))
            else:
                dt = datetime.fromtimestamp(os.path.getmtime(filepath))

            metadata = read_short_metadata(filepath)
            shorts.append({
                "filename": filename,
                "url": f"/api/shorts_video/{filename}",
                "timestamp": dt.isoformat(),
                "date_display": dt.strftime("%d/%m/%Y"),
                "time_display": dt.strftime("%H:%M"),
                "caption": metadata.get("caption", ""),
                "hashtags": metadata.get("hashtags", []),
                "hashtags_text": metadata.get("hashtags_text", ""),
                "news_title": metadata.get("news_title", ""),
                "script": metadata.get("script", ""),
                "theme": metadata.get("theme", ""),
                "mode": metadata.get("mode", ""),
                "social_posts": metadata.get("social_posts", {}),
                "posted_any": metadata.get("posted_any", False),
                "posted_platforms": metadata.get("posted_platforms", []),
            })

        shorts.sort(key=lambda x: x["timestamp"], reverse=True)
        return jsonify({"shorts": shorts})

    @app.route('/api/shorts_video/<path:filename>')
    def serve_short_video(filename):
        shorts_dir = os.path.join(base_dir, "output", "shorts")
        return send_from_directory(shorts_dir, filename)

    @app.route('/api/shorts_delete', methods=['POST'])
    def shorts_delete():
        data = request.json or {}
        raw_filenames = data.get("filenames") or []
        if not isinstance(raw_filenames, list):
            return jsonify({"status": "error", "message": "Payload non valido."}), 400

        filenames = []
        seen = set()
        for value in raw_filenames:
            filename = os.path.basename(str(value or "").strip())
            if not filename or not filename.endswith(".mp4"):
                continue
            if filename in seen:
                continue
            seen.add(filename)
            filenames.append(filename)

        if not filenames:
            return jsonify({"status": "error", "message": "Nessun reel selezionato."}), 400

        shorts_dir = os.path.join(base_dir, "output", "shorts")
        deleted_files = 0
        missing_files = []
        for filename in filenames:
            video_path = os.path.join(shorts_dir, filename)
            metadata_path = os.path.splitext(video_path)[0] + ".json"
            for path in (video_path, metadata_path):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        if path == video_path:
                            deleted_files += 1
                    except Exception as e:
                        return jsonify({"status": "error", "message": f"Eliminazione file fallita per {filename}: {e}"}), 500
                elif path == video_path:
                    missing_files.append(filename)

        deleted_rows = delete_shorts(filenames)
        return jsonify({
            "status": "OK",
            "deleted_files": deleted_files,
            "deleted_rows": deleted_rows,
            "missing_files": missing_files,
        })

