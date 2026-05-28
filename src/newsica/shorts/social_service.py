import os

from newsica.storage.repositories.shorts_library_repository import mark_short_social_posts
from newsica.utils.social_publisher import SocialPublisher


def build_full_caption(caption: str, hashtags: list[str] | str | None) -> str:
    base_caption = str(caption or "").strip()
    if isinstance(hashtags, list):
        hashtags_text = " ".join(str(tag).strip() for tag in hashtags if str(tag).strip())
    else:
        hashtags_text = str(hashtags or "").strip()
    if base_caption and hashtags_text:
        return f"{base_caption}\n\n{hashtags_text}"
    if hashtags_text:
        return hashtags_text
    return base_caption


def publish_short(video_path: str, title: str, caption: str, platform: str) -> dict:
    publisher = SocialPublisher()
    if platform == "youtube":
        return publisher.publish_to_youtube(video_path, title, caption)
    if platform == "instagram":
        return publisher.publish_to_instagram(video_path, caption)
    if platform == "tiktok":
        return publisher.publish_to_tiktok(video_path, title, caption)
    if platform == "all":
        return publisher.publish_to_all_socials(video_path, title, caption)
    raise ValueError("Piattaforma non supportata.")


def schedule_short_to_all(video_path: str, title: str, caption: str, due_at_by_platform: dict) -> dict:
    publisher = SocialPublisher()
    return publisher.schedule_to_all_socials(
        video_path=video_path,
        title=title,
        caption=caption,
        due_at_by_platform=due_at_by_platform,
    )


def _platform_results(platform: str, result: dict) -> dict[str, dict]:
    platform_results = result.get("results")
    if isinstance(platform_results, dict):
        return platform_results
    return {platform: result}


def track_social_posts(filename: str, platform: str, result: dict) -> dict:
    short_filename = os.path.basename(str(filename or "").strip())
    if not short_filename:
        return {}
    return mark_short_social_posts(short_filename, _platform_results(platform, result))
