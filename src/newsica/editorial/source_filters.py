from newsica.domain.characters import CharacterConfig


def filter_items_for_character(items: list[dict], character: CharacterConfig) -> list[dict]:
    sources = set(character.sources)
    if not sources:
        return []
    return [item for item in items if item.get("source", "") in sources]


def fallback_general_news(items: list[dict]) -> list[dict]:
    return [item for item in items if item.get("source") == "ansa_ultimora"]

