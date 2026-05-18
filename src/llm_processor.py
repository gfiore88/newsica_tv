import json
import requests
import os
import sys
import re

# Impostazioni Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:4b" # Modello locale più leggero per non sforzare il Mac


# Percorsi dei file
TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
INPUT_FILE = os.path.join(TMP_DIR, "raw_news.json")
OUTPUT_FILE = os.path.join(TMP_DIR, "script.txt")

PROMPTS = {
    "news": """Sei Chiara, la conduttrice principale di NewsicaTV, una Web TV H24 in diretta.
Il tuo compito è prendere una serie di notizie grezze (in formato JSON) e trasformarle in un copione fluido, professionale e istituzionale, pronto per essere letto ad alta voce.
Linee guida:
1. Inizia sempre con: "Benritrovati in diretta su NewsicaTV. Ecco gli aggiornamenti di oggi."
2. Scrivi in modo discorsivo (frasi brevi, ritmo televisivo).
3. NON fare elenchi puntati. Usa transizioni tra le notizie.
4. Concludi con: "Per questa edizione è tutto. Restate con noi per la nostra programmazione musicale."
5. Produci ESCLUSIVAMENTE il testo del copione.
""",
    "sport": """Sei Leo, il giornalista sportivo di NewsicaTV.
Il tuo compito è prendere le notizie (in formato JSON) e trasformarle in un copione dinamico ed entusiasta.
Linee guida:
1. Inizia sempre con: "Un saluto a tutti gli appassionati di sport! Oggi giornata ricca di emozioni..."
2. Usa un tono energico e termini dinamici.
3. Produci ESCLUSIVAMENTE il testo del copione.
""",
    "meteo": """Sei il Colonnello, l'esperto meteo di NewsicaTV.
Il tuo compito è trasformare le notizie o i dati meteo in un copione rassicurante e tecnico.
Linee guida:
1. Inizia sempre con: "Ed eccoci agli aggiornamenti meteo. Vediamo cosa ci riservano le prossime ore."
2. Usa un tono calmo e preciso.
3. Produci ESCLUSIVAMENTE il testo del copione.
"""
}

# Leggi il personaggio dagli argomenti (default: news)
character = "news"
if len(sys.argv) > 1:
    character = sys.argv[1]

if character not in PROMPTS:
    print(f"⚠️ Personaggio '{character}' non trovato. Uso 'news'.")
    character = "news"

SYSTEM_PROMPT = PROMPTS[character]


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def build_fallback_script(filtered_news):
    if character == "sport":
        opening = "Un saluto a tutti gli appassionati di sport! Oggi giornata ricca di emozioni."
        closing = "Per lo sport è tutto. Restate con noi su NewsicaTV."
    elif character == "meteo":
        opening = "Ed eccoci agli aggiornamenti meteo. Vediamo cosa ci riservano le prossime ore."
        closing = "Per il meteo è tutto. A tra poco con nuovi aggiornamenti."
    else:
        opening = "Benritrovati in diretta su NewsicaTV. Ecco gli aggiornamenti di oggi."
        closing = "Per questa edizione è tutto. Restate con noi per la nostra programmazione musicale."

    lines = [opening]
    for item in filtered_news[:4]:
        title = clean_text(item.get("title", ""))
        summary = clean_text(item.get("summary", ""))
        if title and summary:
            lines.append(f"{title}. {summary}")
        elif title:
            lines.append(title)

    if len(lines) == 1:
        lines.append("Al momento non ci sono nuovi aggiornamenti verificati per questa rubrica.")

    lines.append(closing)
    return "\n\n".join(lines)


def generate_script():
    print("Avvio della rielaborazione editoriale tramite LLM (Ollama locale)...")
    
    if not os.path.exists(INPUT_FILE):
        print(f"Errore: File {INPUT_FILE} non trovato. Esegui prima lo scraper.")
        sys.exit(1)
        
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        try:
            news_items = json.load(f)
        except Exception as e:
            print(f"Errore nella lettura del JSON: {e}")
            sys.exit(1)
            
    # Filtra le notizie in base al personaggio
    filtered_news = []
    for item in news_items:
        source = item.get('source', '')
        if character == "news" and ("ansa_ultimora" in source or "ansa_mondo" in source):
            filtered_news.append(item)
        elif character == "sport" and "sport" in source:
            filtered_news.append(item)
        elif character == "meteo" and "meteo" in source:
            filtered_news.append(item)
            
    # Se non ci sono notizie per quel personaggio, usa quelle generali come fallback
    if not filtered_news:
        print(f"⚠️ Nessuna notizia specifica per '{character}'. Uso quelle generali.")
        filtered_news = [item for item in news_items if "ansa_ultimora" in item.get('source', '')]
        
    # Prepariamo le notizie in testo
    news_text = "Ecco le notizie da rielaborare:\n\n"
    for item in filtered_news:
        news_text += f"- TITOLO: {item['title']}\n"
        news_text += f"  SINTESI: {item['summary']}\n\n"
        
    print(f"Ho letto {len(filtered_news)} notizie per {character}. Invio al modello {MODEL_NAME}...")
    
    fallback_script = build_fallback_script(filtered_news)

    # Payload per Ollama
    payload = {
        "model": MODEL_NAME,
        "system": SYSTEM_PROMPT,
        "prompt": news_text,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=8)
        response.raise_for_status()
        result = response.json()
        script = result.get('response', '').strip()
        if not script:
            print("⚠️ Ollama ha restituito un copione vuoto. Uso fallback locale.")
            script = fallback_script
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(script)
            
        print(f"✅ Copione generato con successo e salvato in {OUTPUT_FILE}")
        print("\n--- ANTEPRIMA COPIONE ---")
        print(script[:300] + "...\n-------------------------")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione a Ollama. Assicurati che l'app Ollama sia avviata. Dettagli: {e}")
        print("⚠️ Uso copione fallback locale per non bloccare la rotazione degli agenti.")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(fallback_script)
        print(f"✅ Copione fallback generato e salvato in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_script()
