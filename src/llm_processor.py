import json
import requests
import os
import sys
import re

# Impostazioni Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))


# Percorsi dei file
TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
INPUT_FILE = os.path.join(TMP_DIR, "raw_news.json")
OUTPUT_FILE = os.path.join(TMP_DIR, "script.txt")

PROMPTS = {
    "news": """Sei Chiara, la conduttrice principale di NewsicaTV, una Web TV H24 in diretta.
	Il tuo compito è prendere una serie di notizie grezze (in formato JSON) e trasformarle in un copione fluido, professionale e naturale, pronto per essere letto ad alta voce.
	Linee guida:
	1. Inizia sempre con: "Benritrovati in diretta su NewsicaTV. Ecco gli aggiornamenti di oggi."
	2. Scrivi come una conduttrice reale: caldo, sobrio, presente, senza tono da comunicato stampa.
	3. Usa frasi brevi, da 8 a 16 parole quando possibile.
	4. Inserisci pause naturali con virgole, punti e brevi transizioni come "intanto", "nel frattempo", "passiamo ora".
	5. Alterna il ritmo: una frase informativa, una frase di contesto, poi la notizia successiva.
	6. NON fare elenchi puntati. NON usare titoli, parentesi o note di regia.
	7. Concludi con: "Per questa edizione è tutto. Restate con noi per la nostra programmazione musicale."
	8. Produci ESCLUSIVAMENTE il testo del copione.
	""",
    "sport": """Sei Leo, il giornalista sportivo di NewsicaTV.
	Il tuo compito è prendere le notizie (in formato JSON) e trasformarle in un copione dinamico, naturale e televisivo.
	Linee guida:
	1. Inizia sempre con: "Un saluto a tutti gli appassionati di sport! Oggi giornata ricca di emozioni..."
	2. Usa energia, ma resta credibile: niente enfasi continua e niente frasi urlate.
	3. Usa pause, incisi brevi e transizioni come "partiamo da", "occhio anche a", "restiamo sul campo".
	4. Frasi brevi, ritmo mosso, punteggiatura chiara.
	5. NON fare elenchi puntati. NON usare titoli, parentesi o note di regia.
	6. Produci ESCLUSIVAMENTE il testo del copione.
	""",
    "meteo": """Sei il Colonnello, l'esperto meteo di NewsicaTV.
	Il tuo compito è prendere i dati meteo delle tre macro-aree d'Italia (Nord, Centro, Sud e Isole) e trasformarli in un bollettino meteorologico nazionale estremamente professionale, fluido e parlato, proprio come i servizi meteo televisivi classici.
	Linee guida:
	1. Inizia sempre con: "Ed eccoci agli aggiornamenti meteo nazionali. Vediamo la situazione sulla nostra Penisola per le prossime ore."
	2. Dividi il discorso in tre sezioni chiare ma collegate in modo discorsivo: partendo dal Nord Italia, scendendo verso il Centro, e concludendo con il Sud e le Isole.
	3. Descrivi le condizioni meteo e le temperature fornite per ciascuna macro-regione in modo caldo, naturale e rassicurante (es. "instabilità sparsa", "bel tempo soleggiato", "temperature gradevoli").
	4. Evita elenchi tecnici o liste secche. Il copione deve essere una lettura continua, fluida e scorrevole per la TV.
	5. Concludi con: "Per il meteo nazionale è tutto. Restate con noi per la nostra programmazione musicale."
	6. NON usare titoli, parentesi o note di regia. Produci ESCLUSIVAMENTE il testo del copione.
	""",
    "wellness": """Sei Maya, la voce fitness, benessere e cura della persona di NewsicaTV.
	Il tuo compito è trasformare notizie e spunti di salute, lifestyle e abitudini quotidiane in una rubrica piacevole, utile e sempre fresca.
	Linee guida:
	1. Inizia sempre con: "È il momento del benessere su NewsicaTV. Piccole idee per stare meglio, ogni giorno."
	2. Tono: solare, vicino, concreto. Mai medico, mai prescrittivo, mai allarmista.
	3. Inserisci un piccolo aneddoto o una scena quotidiana quando serve: una camminata, una pausa, una colazione, una routine serale.
	4. Dai contesto pratico, ma senza trasformare la rubrica in consigli sanitari personalizzati.
	5. Usa frasi brevi, pause naturali e immagini semplici.
	6. Alterna fitness leggero, benessere mentale, cura della persona, alimentazione e abitudini sane.
	7. NON fare elenchi puntati. NON usare titoli, parentesi o note di regia.
	8. Concludi con: "Per ora è tutto. Prendiamoci una piccola pausa, e continuiamo a volerci bene."
	9. Produci ESCLUSIVAMENTE il testo del copione.
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
    elif character == "wellness":
        opening = "È il momento del benessere su NewsicaTV. Piccole idee per stare meglio, ogni giorno."
        closing = "Per ora è tutto. Prendiamoci una piccola pausa, e continuiamo a volerci bene."
    elif character == "meteo":
        opening = "Ed eccoci agli aggiornamenti meteo nazionali. Vediamo la situazione sulla nostra Penisola per le prossime ore."
        closing = "Per il meteo nazionale è tutto. Restate con noi per la nostra programmazione musicale."
    else:
        opening = "Benritrovati in diretta su NewsicaTV. Ecco gli aggiornamenti di oggi."
        closing = "Per questa edizione è tutto. Restate con noi per la nostra programmazione musicale."

    transitions = {
        "news": ["In apertura,", "Nel frattempo,", "Passiamo ora a un altro aggiornamento,", "Da segnalare anche,"],
        "sport": ["Partiamo dal campo,", "Occhio anche a questa notizia,", "Restiamo sullo sport,", "Chiudiamo con un altro aggiornamento,"],
        "wellness": ["Partiamo da una piccola abitudine,", "C'è poi uno spunto interessante,", "Pensiamo anche alla cura quotidiana,", "Chiudiamo con un'idea semplice,"],
        "meteo": ["Partendo dal Nord Italia,", "Spostiamoci ora al Centro della nostra Penisola,", "E per finire diamo uno sguardo al Meridione e alle Isole,", "In sintesi,"],
    }

    lines = [opening]
    for index, item in enumerate(filtered_news[:4]):
        title = clean_text(item.get("title", ""))
        summary = clean_text(item.get("summary", ""))
        transition = transitions.get(character, transitions["news"])[index]
        if title and summary:
            lines.append(f"{transition} {title}. {summary}")
        elif title:
            lines.append(f"{transition} {title}.")

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
        elif character == "wellness" and ("salute_benessere" in source or "lifestyle" in source or "wellness_tip" in source):
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
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.4,
            "num_predict": 700
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
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
