from __future__ import annotations


GENERAL_NEWS_MARKERS = (
    "news",
    "edizione",
    "edition",
    "tg",
    "notizie",
    "aggiornamenti",
    "riepilogo",
    "punto",
)


def normalize_title(title: str | None) -> str:
    return " ".join((title or "").strip().split())


def is_general_news_title(title: str | None) -> bool:
    normalized = normalize_title(title).lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in GENERAL_NEWS_MARKERS)
