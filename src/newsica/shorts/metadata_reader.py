import json
import os

from newsica.storage.repositories.shorts_library_repository import get_short


def normalize_short_hashtags(raw_hashtags):
    if not isinstance(raw_hashtags, list):
        return []
    hashtags = []
    seen = set()
    for value in raw_hashtags:
        tag = str(value or "").strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        lowered = tag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        hashtags.append(tag)
        if len(hashtags) == 5:
            break
    return hashtags


def normalize_short_social_posts(raw_social_posts):
    if not isinstance(raw_social_posts, dict):
        return {}
    normalized = {}
    for platform in ("youtube", "instagram", "tiktok"):
        payload = raw_social_posts.get(platform)
        if not isinstance(payload, dict):
            continue
        posted_at = str(payload.get("posted_at", "")).strip()
        message = str(payload.get("message", "")).strip()
        if not posted_at:
            continue
        normalized[platform] = {
            "posted_at": posted_at,
            "message": message,
        }
    return normalized


def read_short_metadata(video_path):
    filename = os.path.basename(video_path)
    db_row = get_short(filename)
    if db_row:
        try:
            raw_hashtags = json.loads(db_row.get("hashtags_json") or "[]")
        except Exception:
            raw_hashtags = []
        try:
            raw_social_posts = json.loads(db_row.get("social_posts_json") or "{}")
        except Exception:
            raw_social_posts = {}
        hashtags = normalize_short_hashtags(raw_hashtags)
        social_posts = normalize_short_social_posts(raw_social_posts)
        return {
            "caption": str(db_row.get("caption", "")).strip(),
            "hashtags": hashtags,
            "hashtags_text": " ".join(hashtags),
            "news_title": str(db_row.get("news_title", "")).strip(),
            "script": str(db_row.get("script", "")).strip(),
            "theme": str(db_row.get("theme", "")).strip(),
            "mode": str(db_row.get("mode", "")).strip(),
            "social_posts": social_posts,
            "posted_any": bool(social_posts),
            "posted_platforms": sorted(social_posts.keys()),
        }

    metadata_path = os.path.splitext(video_path)[0] + ".json"
    if not os.path.exists(metadata_path):
        return {}
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {}

    hashtags = normalize_short_hashtags(payload.get("hashtags"))
    return {
        "caption": str(payload.get("caption", "")).strip(),
        "hashtags": hashtags,
        "hashtags_text": " ".join(hashtags),
        "news_title": str(payload.get("news_title", "")).strip(),
        "script": str(payload.get("script", "")).strip(),
        "theme": str(payload.get("theme", "")).strip(),
        "mode": str(payload.get("mode", "")).strip(),
        "social_posts": {},
        "posted_any": False,
        "posted_platforms": [],
    }

