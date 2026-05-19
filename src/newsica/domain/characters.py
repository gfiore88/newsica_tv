from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from newsica.config.paths import ASSETS_DIR

CHARACTERS_FILE = Path(__file__).with_name("characters.json")


@dataclass(frozen=True)
class CharacterConfig:
    id: str
    display_name: str
    rubric_type: str
    voice: str
    speed: float
    prompt: str | None
    sources: tuple[str, ...]
    jingle: str | None
    jingle_label: str
    intro_template: str
    accent: str
    format: str

    @property
    def jingle_path(self) -> str | None:
        if not self.jingle:
            return None
        return str(ASSETS_DIR.parent / self.jingle)

    def render_intro(self, title: str) -> str:
        return self.intro_template.format(title=title)

    def read_prompt(self) -> str:
        if not self.prompt:
            return ""
        prompt_path = Path(__file__).resolve().parents[1] / self.prompt
        return prompt_path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_characters() -> dict[str, CharacterConfig]:
    data = json.loads(CHARACTERS_FILE.read_text(encoding="utf-8"))
    characters = {}
    for item in data["characters"]:
        character = CharacterConfig(
            id=item["id"],
            display_name=item["display_name"],
            rubric_type=item["rubric_type"],
            voice=item["voice"],
            speed=float(item["speed"]),
            prompt=item.get("prompt"),
            sources=tuple(item.get("sources", [])),
            jingle=item.get("jingle"),
            jingle_label=item.get("jingle_label", "jingle NewsicaTV"),
            intro_template=item.get("intro_template", "Comincia {title}, una rubrica di NewsicaTV."),
            accent=item.get("accent", "0xef4444"),
            format=item.get("format", "single_part"),
        )
        characters[character.id] = character
    return characters


def get_character(character_id: str, default: str = "news") -> CharacterConfig:
    characters = load_characters()
    return characters.get(character_id) or characters[default]


def known_character_ids() -> tuple[str, ...]:
    return tuple(load_characters().keys())

