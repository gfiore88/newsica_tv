from pathlib import Path

from newsica.config.paths import JINGLES_DIR
from newsica.domain.characters import get_character

CLASSIC_JINGLE_FILE = JINGLES_DIR / "newsicatv_jingle.mp3"


def get_jingle_for_block(block_type):
    character = get_character(block_type)
    jingle_file = Path(character.jingle_path) if character.jingle_path else CLASSIC_JINGLE_FILE
    if not jingle_file.exists():
        jingle_file = CLASSIC_JINGLE_FILE
    return str(jingle_file), character.jingle_label

