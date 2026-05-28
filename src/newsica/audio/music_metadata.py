import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Callable


@lru_cache(maxsize=256)
def probe_music_tags(track_path_str: str) -> tuple[str, str]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format_tags=title,artist",
                "-of",
                "json",
                track_path_str,
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return "", ""

    if result.returncode != 0 or not result.stdout:
        return "", ""

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "", ""

    tags = payload.get("format", {}).get("tags", {})
    artist = " ".join(str(tags.get("artist", "")).split())
    title = " ".join(str(tags.get("title", "")).split())
    return artist, title


def read_music_tags(
    track_path: Path,
    ai_music_dir: Path,
    probe_tags: Callable[[str], tuple[str, str]] = probe_music_tags,
) -> tuple[str, str]:
    if track_path.parent.resolve() == ai_music_dir.resolve():
        return "", ""
    return probe_tags(str(track_path))


def read_ai_sidecar_title(
    track_path: Path,
    ai_music_dir: Path,
    track_title_resolver: Callable[[str], str],
) -> str:
    try:
        if track_path.parent.resolve() != ai_music_dir.resolve():
            return ""
    except Exception:
        return ""

    sidecar_path = track_path.with_suffix(".meta")
    if sidecar_path.exists():
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
            title = " ".join(str(payload.get("title", "")).split())
            if title:
                return title
        except Exception:
            pass

    return track_title_resolver(str(track_path))


def display_title_for_music_file(
    music_file: str,
    ai_music_dir: Path,
    read_ai_sidecar_title_fn: Callable[[Path], str],
    read_music_tags_fn: Callable[[Path], tuple[str, str]],
) -> str:
    if not music_file:
        return ""

    track_path = Path(music_file)
    ai_sidecar_title = read_ai_sidecar_title_fn(track_path)
    if ai_sidecar_title:
        return ai_sidecar_title

    artist, title = read_music_tags_fn(track_path)

    if artist and title:
        return f"{artist} - {title}"

    if title:
        return title

    if track_path.parent.resolve() == ai_music_dir.resolve():
        return "Newsica AI Track"

    fallback_title = track_path.stem.replace("_", " ").strip()
    return " ".join(fallback_title.split())


def build_music_metadata(
    music_file: str,
    current_state: dict | None,
    title_resolver: Callable[[str], str],
) -> dict:
    state = dict(current_state or {})
    state["current_music_title"] = title_resolver(music_file)
    return state


def build_post_telegram_restore_metadata(
    previous_state: dict | None,
    bg_music: str | None,
    metadata_builder: Callable[[str, dict | None], dict],
) -> dict:
    restored = dict(previous_state or {})
    if bg_music:
        restored = metadata_builder(bg_music, restored)
    restored["requested_by"] = ""
    restored["requested_title"] = ""
    return restored
