from newsica.domain.characters import CharacterConfig
from newsica.sources.loader import load_sources_registry


def filter_items_for_character(items: list[dict], character: CharacterConfig) -> list[dict]:
    sources = set(character.sources)
    if not sources:
        return []
    return [item for item in items if item.get("source", "") in sources]


def fallback_general_news(items: list[dict]) -> list[dict]:
    news_sources = load_sources_registry()["news_sources"]
    return [item for item in items if item.get("source") in news_sources]
