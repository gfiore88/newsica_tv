import glob
import os
import random
import re
from datetime import datetime

from newsica.shorts.constants import SHORT_MODES
from newsica.shorts.metadata_reader import read_short_metadata
from newsica.storage.repositories.shorts_library_repository import delete_shorts, mark_short_social_posts


def normalize_short_mode(raw_mode: str) -> str | None:
    mode = str(raw_mode or "news").strip().lower() or "news"
    if mode == "random":
        mode = random.choice(list(SHORT_MODES))
    if mode not in set(SHORT_MODES):
        return None
    return mode


def generate_short_payload(mode: str) -> tuple[dict, int]:
    valid_mode = normalize_short_mode(mode)
    if not valid_mode:
        return {"status": "error", "message": "Modalità short non valida."}, 400
    try:
        from newsica.agents.shorts_agent import ShortsAgent

        agent = ShortsAgent()
        result = agent.run(mode=valid_mode)
        if result.get("status") == "success":
            output_file = result.get("output", "")
            filename = os.path.basename(output_file) if output_file else ""
            result["filename"] = filename
            result["video_url"] = f"/api/shorts_video/{filename}" if filename else ""
            return result, 200
        return result, 500
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


def publish_short_payload(base_dir: str, filename: str, platform: str) -> tuple[dict, int]:
    if not filename or not platform:
        return {"status": "error", "message": "Parametri mancanti."}, 400

    shorts_dir = os.path.join(base_dir, "output", "shorts")
    video_path = os.path.join(shorts_dir, filename)
    if not os.path.exists(video_path):
        return {"status": "error", "message": "File video non trovato."}, 404

    metadata = read_short_metadata(video_path)
    title = metadata.get("news_title", "Short NewsicaTV")
    caption = metadata.get("caption", "")
    hashtags = metadata.get("hashtags_text", "")
    full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption

    from newsica.utils.social_publisher import SocialPublisher

    publisher = SocialPublisher()
    if platform == "youtube":
        result = publisher.publish_to_youtube(video_path, title, full_caption)
    elif platform == "instagram":
        result = publisher.publish_to_instagram(video_path, full_caption)
    elif platform == "tiktok":
        result = publisher.publish_to_tiktok(video_path, title, full_caption)
    elif platform == "all":
        result = publisher.publish_to_all_socials(video_path, title, full_caption)
    else:
        return {"status": "error", "message": "Piattaforma non supportata."}, 400

    platform_results = result.get("results")
    if not isinstance(platform_results, dict):
        platform_results = {platform: result}
    social_posts = mark_short_social_posts(filename, platform_results)

    if result.get("status") == "success":
        return {"status": "OK", "message": result.get("message"), "social_posts": social_posts}, 200
    if result.get("status") == "partial":
        return {"status": "partial", "message": result.get("message"), "results": result.get("results", {}), "social_posts": social_posts}, 200
    return {
        "status": result.get("status", "config_missing"),
        "message": result.get("message"),
        "results": result.get("results", {}),
        "social_posts": social_posts,
    }, 200


def list_shorts_payload(base_dir: str) -> dict:
    shorts_dir = os.path.join(base_dir, "output", "shorts")
    if not os.path.exists(shorts_dir):
        return {"shorts": []}

    shorts = []
    for filepath in glob.glob(os.path.join(shorts_dir, "*.mp4")):
        filename = os.path.basename(filepath)

        match = re.search(r"short_(\d{8})_(\d{6})", filename)
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
        shorts.append(
            {
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
            }
        )

    shorts.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"shorts": shorts}


def delete_shorts_payload(base_dir: str, raw_filenames) -> tuple[dict, int]:
    if not isinstance(raw_filenames, list):
        return {"status": "error", "message": "Payload non valido."}, 400

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
        return {"status": "error", "message": "Nessun reel selezionato."}, 400

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
                    return {"status": "error", "message": f"Eliminazione file fallita per {filename}: {e}"}, 500
            elif path == video_path:
                missing_files.append(filename)

    deleted_rows = delete_shorts(filenames)
    return {
        "status": "OK",
        "deleted_files": deleted_files,
        "deleted_rows": deleted_rows,
        "missing_files": missing_files,
    }, 200

