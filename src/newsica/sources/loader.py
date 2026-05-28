"""Loader e persistenza delle fonti RSS direttamente su registry.py.

`registry.py` resta la fonte di verita' editoriale. La dashboard puo':
- leggere le fonti attive;
- aggiungere/rimuovere feed;
- vederne l'anteprima live.

La regia vede le modifiche "a caldo" perche' il collector rilegge il registry
dal filesystem a ogni raccolta, senza affidarsi al modulo gia' importato.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from pprint import pformat

_REGISTRY_PATH = Path(__file__).with_name("registry.py")
_GENERAL_NEWS_CATEGORIES = {"breaking", "cultura", "economia", "general", "news", "tech"}


def _load_registry_module():
    spec = importlib.util.spec_from_file_location("newsica_dynamic_sources_registry", _REGISTRY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossibile caricare il registry fonti da {_REGISTRY_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_feed_definitions(module) -> dict[str, dict]:
    definitions = getattr(module, "RSS_FEED_DEFINITIONS", None)
    if isinstance(definitions, dict):
        normalized = {}
        for feed_id, entry in definitions.items():
            if isinstance(entry, dict) and entry.get("url"):
                normalized[str(feed_id)] = {
                    "url": str(entry["url"]).strip(),
                    "category": str(entry.get("category", "news")).strip().lower() or "news",
                }
        if normalized:
            return normalized

    legacy_feeds = getattr(module, "RSS_FEEDS", {})
    normalized = {}
    for feed_id, url in legacy_feeds.items():
        normalized[str(feed_id)] = {
            "url": str(url).strip(),
            "category": _infer_category(str(feed_id)),
        }
    return normalized


def load_sources_registry() -> dict:
    module = _load_registry_module()
    definitions = _normalize_feed_definitions(module)

    return {
        "feeds": definitions,
        "news_sources": {
            feed_id
            for feed_id, entry in definitions.items()
            if entry.get("category", "news") in _GENERAL_NEWS_CATEGORIES
        },
        "sport_sources": {
            feed_id for feed_id, entry in definitions.items() if entry.get("category") == "sport"
        },
        "wellness_sources": {
            feed_id for feed_id, entry in definitions.items() if entry.get("category") == "wellness"
        },
        "motori_sources": {
            feed_id for feed_id, entry in definitions.items() if entry.get("category") == "motori"
        },
        "news_preferred_sources": list(getattr(module, "NEWS_PREFERRED_SOURCES", [])),
        "sport_preferred_sources": list(getattr(module, "SPORT_PREFERRED_SOURCES", [])),
        "wellness_preferred_sources": list(getattr(module, "WELLNESS_PREFERRED_SOURCES", [])),
        "motori_preferred_sources": list(getattr(module, "MOTORI_PREFERRED_SOURCES", [])),
        "news_rotation_limit": int(getattr(module, "NEWS_ROTATION_LIMIT", 10)),
        "sport_rotation_limit": int(getattr(module, "SPORT_ROTATION_LIMIT", 4)),
        "motori_rotation_limit": int(getattr(module, "MOTORI_ROTATION_LIMIT", 4)),
    }


def load_rss_feeds() -> dict[str, str]:
    registry = load_sources_registry()
    return {
        feed_id: entry["url"]
        for feed_id, entry in registry["feeds"].items()
    }


def load_all_sources_detail() -> list[dict]:
    registry = load_sources_registry()
    return [
        {
            "id": feed_id,
            "url": entry["url"],
            "category": entry.get("category", "news"),
        }
        for feed_id, entry in sorted(registry["feeds"].items())
    ]


def add_source(feed_id: str, url: str, category: str = "news") -> dict:
    registry = load_sources_registry()
    registry["feeds"][feed_id] = {
        "url": url.strip(),
        "category": (category or "news").strip().lower(),
    }
    _write_registry_file(registry)
    return registry["feeds"][feed_id]


def remove_source(feed_id: str) -> bool:
    registry = load_sources_registry()
    if feed_id not in registry["feeds"]:
        return False
    del registry["feeds"][feed_id]
    _write_registry_file(registry)
    return True


def _write_registry_file(registry: dict) -> None:
    feeds = {
        feed_id: {
            "url": entry["url"],
            "category": entry.get("category", "news"),
        }
        for feed_id, entry in sorted(registry["feeds"].items())
    }

    existing_feed_ids = set(feeds)

    def _filtered_preferred(key: str) -> list[str]:
        return [feed_id for feed_id in registry.get(key, []) if feed_id in existing_feed_ids]

    content = "\n".join(
        [
            f"RSS_FEED_DEFINITIONS = {pformat(feeds, width=100, sort_dicts=True)}",
            "",
            f"GENERAL_NEWS_CATEGORIES = {pformat(_GENERAL_NEWS_CATEGORIES, width=100)}",
            "",
            "RSS_FEEDS = {",
            '    feed_id: entry["url"]',
            "    for feed_id, entry in RSS_FEED_DEFINITIONS.items()",
            "}",
            "",
            "NEWS_SOURCES = {",
            "    feed_id",
            "    for feed_id, entry in RSS_FEED_DEFINITIONS.items()",
            '    if entry.get("category", "news") in GENERAL_NEWS_CATEGORIES',
            "}",
            "",
            "SPORT_SOURCES = {",
            "    feed_id",
            "    for feed_id, entry in RSS_FEED_DEFINITIONS.items()",
            '    if entry.get("category") == "sport"',
            "}",
            "",
            "WELLNESS_SOURCES = {",
            "    feed_id",
            "    for feed_id, entry in RSS_FEED_DEFINITIONS.items()",
            '    if entry.get("category") == "wellness"',
            "}",
            "",
            "MOTORI_SOURCES = {",
            "    feed_id",
            "    for feed_id, entry in RSS_FEED_DEFINITIONS.items()",
            '    if entry.get("category") == "motori"',
            "}",
            "",
            f"NEWS_PREFERRED_SOURCES = {pformat(_filtered_preferred('news_preferred_sources'), width=100)}",
            f"SPORT_PREFERRED_SOURCES = {pformat(_filtered_preferred('sport_preferred_sources'), width=100)}",
            f"WELLNESS_PREFERRED_SOURCES = tuple({pformat(_filtered_preferred('wellness_preferred_sources'), width=100)})",
            f"MOTORI_PREFERRED_SOURCES = {pformat(_filtered_preferred('motori_preferred_sources'), width=100)}",
            "",
            f"NEWS_ROTATION_LIMIT = {int(registry.get('news_rotation_limit', 10))}",
            f"SPORT_ROTATION_LIMIT = {int(registry.get('sport_rotation_limit', 4))}",
            f"MOTORI_ROTATION_LIMIT = {int(registry.get('motori_rotation_limit', 4))}",
            "",
            "",
            "def max_items_for_source(source):",
            '    return 12 if source in NEWS_SOURCES else 8',
            "",
        ]
    )
    _REGISTRY_PATH.write_text(content, encoding="utf-8")


def _infer_category(feed_id: str) -> str:
    if "sport" in feed_id:
        return "sport"
    if "meteo" in feed_id or "weather" in feed_id:
        return "meteo"
    if "salute" in feed_id or "benessere" in feed_id or "lifestyle" in feed_id or "wellness" in feed_id:
        return "wellness"
    if "motori" in feed_id:
        return "motori"
    if "tecnologia" in feed_id or "innovazione" in feed_id or "tech" in feed_id:
        return "tech"
    if "cultura" in feed_id:
        return "cultura"
    if "economia" in feed_id:
        return "economia"
    if "ultimora" in feed_id or "breaking" in feed_id:
        return "breaking"
    return "news"
