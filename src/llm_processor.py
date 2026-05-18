import json
import requests
import os
import sys

# Impostazioni Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:4b" # Modello locale più leggero per non sforzare il Mac


# Percorsi dei file
TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
INPUT_FILE = os.path.join(TMP_DIR, "raw_news.json")
OUTPUT_FILE = os.path.join(TMP_DIR, "script.txt")

SYSTEM_PROMPT = """Sei lo speaker principale di NewsicaTV, una Web TV H24 in diretta.
Il tuo compito è prendere una serie di notizie grezze (in formato JSON) e trasformarle in un copione fluido, professionale e coinvolgente, pronto per essere letto ad alta voce.
Linee guida tassative:
1. Inizia sempre con una sigla parlata tipo: "Benritrovati in diretta su NewsicaTV. Ecco gli aggiornamenti di oggi."
2. Scrivi in modo estremamente discorsivo e radiofonico (frasi brevi, ritmo televisivo).
3. NON fare elenchi puntati. Usa transizioni tra le notizie (es. "Passiamo ora agli esteri...", "Cambiando decisamente argomento...").
4. Concludi sempre con una formula di chiusura tipo: "Per questa edizione è tutto. Restate con noi per la nostra programmazione musicale."
5. Produci ESCLUSIVAMENTE il testo del copione, senza commenti o preamboli.
"""

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
            
    # Prepariamo le notizie in testo
    news_text = "Ecco le notizie da rielaborare:\n\n"
    for item in news_items:
        news_text += f"- TITOLO: {item['title']}\n"
        news_text += f"  SINTESI: {item['summary']}\n\n"
        
    print(f"Ho letto {len(news_items)} notizie. Invio al modello {MODEL_NAME}...")
    
    # Payload per Ollama
    payload = {
        "model": MODEL_NAME,
        "system": SYSTEM_PROMPT,
        "prompt": news_text,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        script = result.get('response', '').strip()
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(script)
            
        print(f"✅ Copione generato con successo e salvato in {OUTPUT_FILE}")
        print("\n--- ANTEPRIMA COPIONE ---")
        print(script[:300] + "...\n-------------------------")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore di connessione a Ollama. Assicurati che l'app Ollama sia avviata. Dettagli: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_script()
