import json
import os
import sys

import requests

from newsica.config.paths import TMP_DIR
from newsica.domain.characters import get_character, known_character_ids
from newsica.editorial.fallback_scripts import build_fallback_script
from newsica.editorial.source_filters import fallback_general_news, filter_items_for_character
from newsica.editorial.title_rules import is_general_news_title

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))

INPUT_FILE = TMP_DIR / "raw_news.json"
OUTPUT_FILE = TMP_DIR / "script.txt"


def resolve_character():
    character_id = sys.argv[1] if len(sys.argv) > 1 else "news"
    if character_id not in known_character_ids():
        print(f"⚠️ Personaggio '{character_id}' non trovato. Uso 'news'.")
        character_id = "news"
    return get_character(character_id)


def load_news_items():
    if not INPUT_FILE.exists():
        print(f"Errore: File {INPUT_FILE} non trovato. Esegui prima lo scraper.")
        sys.exit(1)

    try:
        return json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Errore nella lettura del JSON: {e}")
        sys.exit(1)


def resolve_title():
    if len(sys.argv) > 2:
        return sys.argv[2]
    return os.getenv("NEWSICA_BLOCK_TITLE", "")


def build_prompt_payload(news_items, title=None, character_id=None):
    news_text = ""
    if title:
        news_text += (
            "TEMA OBBLIGATORIO DELLA PUNTATA:\n"
            f"{title}\n\n"
            "Regola editoriale: il copione deve rispettare questo titolo. "
            "Usa gli spunti sotto solo se aiutano il tema; non cambiare argomento "
            "e non trasformare la puntata in una rassegna generica.\n\n"
        )
        if character_id == "wellness":
            news_text += (
                "Per una rubrica wellness, traduci il tema in consigli pratici, "
                "sicuri e quotidiani. Se il titolo parla di esercizi per l'ufficio, "
                "concentrati su movimenti semplici da scrivania, postura, pause attive "
                "e respirazione, senza prescrizioni mediche.\n\n"
            )
        if character_id == "news":
            if is_general_news_title(title):
                news_text += (
                    "Questa e' un'edizione news generalista. E' corretto costruire una scaletta mista con "
                    "cronaca, politica, esteri, economia, cultura, tecnologia e sport, mantenendo un tono da "
                    "telegiornale e senza trasformarla in una rubrica monotematica.\n\n"
                )
            else:
                news_text += (
                    "Questa e' una rubrica news tematica. Usa solo spunti coerenti con il titolo e scarta "
                    "le notizie che portano fuori argomento. Il titolo non e' decorativo.\n\n"
                )

    news_text += "Ecco le notizie o gli spunti da rielaborare:\n\n"
    for item in news_items:
        news_text += f"- TITOLO: {item.get('title', '')}\n"
        news_text += f"  SINTESI: {item.get('summary', '')}\n\n"
    return news_text


def write_script(script):
    OUTPUT_FILE.write_text(script, encoding="utf-8")
    print(f"✅ Copione generato con successo e salvato in {OUTPUT_FILE}")
    print("\n--- ANTEPRIMA COPIONE ---")
    print(script[:300] + "...\n-------------------------")


def generate_script():
    print("Avvio della rielaborazione editoriale tramite LLM (Ollama locale)...")

    character = resolve_character()
    title = resolve_title()
    news_items = load_news_items()
    filtered_news = filter_items_for_character(news_items, character)

    if not filtered_news:
        print(f"⚠️ Nessuna notizia specifica per '{character.id}'. Uso quelle generali.")
        filtered_news = fallback_general_news(news_items)

    print(f"Ho letto {len(filtered_news)} notizie per {character.id}. Invio al modello {MODEL_NAME}...")

    fallback_script = build_fallback_script(character.id, filtered_news, title=title)
    payload = {
        "model": MODEL_NAME,
        "system": character.read_prompt(),
        "prompt": build_prompt_payload(filtered_news, title=title, character_id=character.id),
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.4,
            "num_predict": 1000,
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        script = response.json().get("response", "").strip()
        if not script:
            print("⚠️ Ollama ha restituito un copione vuoto. Uso fallback locale.")
            script = fallback_script
        write_script(script)
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione a Ollama. Assicurati che l'app Ollama sia avviata. Dettagli: {e}")
        print("⚠️ Uso copione fallback locale per non bloccare la rotazione degli agenti.")
        write_script(fallback_script)


if __name__ == "__main__":
    generate_script()
