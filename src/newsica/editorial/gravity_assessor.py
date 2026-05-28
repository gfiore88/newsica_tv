import os
import re
import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "10"))  # timeout basso per non bloccare lo scraping

HIGH_GRAVITY_KEYWORDS = [
    r"terremoto", r"attentato", r"strage", r"guerra", r"escalation", r"esplosione",
    r"alluvione", r"crollo", r"morte di", r"crisi di governo", r"incendio grave",
    r"incidente ferroviario", r"vittime", r"decessi", r"ucciso", r"sparatoria",
    r"terrorismo", r"arresto eccellente", r"catastrofe", r"tsunami", r"missil", r"attacco"
]

MEDIUM_GRAVITY_KEYWORDS = [
    r"sciopero", r"inflazione", r"protesta", r"maltempo", r"accordo", r"riforma",
    r"investito", r"rapina", r"scontro", r"blocco", r"allerta", r"arrestat"
]

def calculate_heuristic_score(title, summary="", category="news"):
    title_lower = title.lower()
    summary_lower = summary.lower() if summary else ""
    full_text = f"{title_lower} {summary_lower}"
    
    # Punteggio di base per categoria
    score = 15
    if category == "sport" or category == "wellness" or category == "motori":
        score = 2
    elif category == "meteo":
        score = 10
    
    # Scansione parole ad alta gravità
    high_matches = 0
    for kw in HIGH_GRAVITY_KEYWORDS:
        if re.search(kw, full_text):
            high_matches += 1
            score += 35
            
    # Scansione parole a media gravità
    medium_matches = 0
    for kw in MEDIUM_GRAVITY_KEYWORDS:
        if re.search(kw, full_text):
            medium_matches += 1
            score += 15
            
    # Bonus per lettere maiuscole o enfasi
    if title.isupper():
        score += 8
    if "!" in title:
        score += 5
        
    return min(100, max(0, score))

def validate_severity_with_llm(title, summary=""):
    prompt = f"""Sei il Redattore Capo di NewsicaTV. Valuta la gravità di questa notizia da 0 a 100 per decidere se merita una Edizione Straordinaria (SPECIAL_BROADCAST).
Una Edizione Straordinaria (score >= 90) deve essere riservata SOLO a disastri naturali gravissimi, attentati di grandi dimensioni, guerre o escalation militari critiche, morti di capi di stato importanti, o emergenze nazionali/internazionali reali.
Notizie di cronaca ordinaria, gossip, sport, scioperi, proteste o politica standard devono avere uno score basso (sotto 50).

Titolo Notizia: {title}
Sintesi Notizia: {summary}

Rispondi in formato JSON puro con le seguenti chiavi:
{{
  "severity_score": <int da 0 a 100>,
  "is_real_emergency": <true o false>,
  "reason": "<una breve motivazione in una frase>"
}}
Non aggiungere altri testi prima o dopo il JSON, restituisci solo il codice JSON valido.
"""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 150,
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        response_text = response.json().get("response", "").strip()
        
        # Pulisce l'output da markdown tipo ```json ... ```
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            json_text = match.group(0)
            data = json.loads(json_text)
            return {
                "severity_score": int(data.get("severity_score", 0)),
                "is_real_emergency": bool(data.get("is_real_emergency", False)),
                "reason": data.get("reason", "Nessuna motivazione fornita.")
            }
    except Exception as e:
        print(f"⚠️ Errore durante la validazione LLM locale: {e}")
        
    return None

def assess_news_gravity(title, summary="", category="news"):
    heuristic = calculate_heuristic_score(title, summary, category)
    
    # Se il punteggio euristico indica una possibile breaking/straordinaria (>= 50),
    # chiamiamo Ollama locale per validare ed evitare falsi positivi.
    if heuristic >= 50:
        print(f"🔍 [GravityAssessor] Punteggio euristico elevato ({heuristic}/100) per: '{title}'. Valuto con LLM...")
        llm_val = validate_severity_with_llm(title, summary)
        if llm_val:
            score = llm_val["severity_score"]
            is_emergency = llm_val["is_real_emergency"]
            reason = llm_val["reason"]
            print(f"🧠 [GravityAssessor] Risposta LLM - Score: {score}, Emergenza: {is_emergency}, Motivo: {reason}")
            return score, is_emergency, reason
            
    # Negli altri casi ci fidiamo dell'euristica veloce
    is_emergency = heuristic >= 90
    return heuristic, is_emergency, "Valutazione euristica rapida"
