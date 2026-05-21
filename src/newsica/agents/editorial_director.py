import os
import json
import logging
import requests
from datetime import date
from newsica.utils.audit_logger import log_decision

logger = logging.getLogger(__name__)

class EditorialDirectorAgent:
    """
    Il "Cervello Pensante" di NewsicaTV.
    Usa Ollama per inventare un palinsesto giornaliero imprevedibile e dinamico.
    """
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = os.getenv("OLLAMA_MODEL", "gemma3:12b")
        
        # Palinsesto di emergenza in caso di crash dell'LLM
        self.fallback_schedule = {
            "00:00": {"title": "Newsica Night", "type": "music_only"},
            "06:00": {"title": "Morning News", "type": "news"},
            "08:00": {"title": "Sport Flash", "type": "sport"},
            "09:00": {"title": "Mondo in 60 Secondi", "type": "flash_60s"},
            "10:00": {"title": "Meteo Update", "type": "meteo"},
            "12:00": {"title": "Pranzo News", "type": "news"},
            "14:00": {"title": "Pomeriggio Sport", "type": "sport"},
            "15:00": {"title": "Newsica Podcast", "type": "podcast"},
            "16:00": {"title": "Tech in 60 Secondi", "type": "flash_60s"},
            "18:00": {"title": "Riepilogo Giornata", "type": "news"},
            "20:00": {"title": "Newsica Sera", "type": "news"},
            "21:00": {"title": "Newsica Podcast", "type": "podcast"},
            "22:00": {"title": "Meteo Notte", "type": "meteo"}
        }

    def get_daily_pillars(self) -> dict:
        return {
            "07:00": {"title": "Morning News: Il Risveglio", "type": "news"},
            "13:00": {"title": "Pranzo News: Il Punto delle 13", "type": "news"},
            "20:00": {"title": "Newsica Sera: Il TG Principale", "type": "news"}
        }

    def get_weekly_appointments(self, current_date: date) -> dict:
        weekday = current_date.weekday()
        appointments = {}
        # 0=Lunedì, 1=Martedì, 2=Mercoledì, 3=Giovedì, 4=Venerdì, 5=Sabato, 6=Domenica
        if weekday == 4: # Venerdì
            appointments["21:00"] = {"title": "Speciale Tecnologia (Settimanale)", "type": "podcast"}
        elif weekday == 6: # Domenica
            appointments["10:00"] = {"title": "Domenica Sport e Benessere", "type": "wellness"}
        return appointments

    def generate_dynamic_schedule(self) -> dict:
        logger.info(f"🧠 [EditorialDirectorAgent] Inizio brainstorming per il palinsesto dinamico...")
        
        today = date.today()
        pillars = self.get_daily_pillars()
        weekly = self.get_weekly_appointments(today)
        fixed_slots = {**pillars, **weekly}
        fixed_slots_str = json.dumps(fixed_slots, indent=2)
        
        system_prompt = f"""Sei l'Agente Direttore Editoriale di NewsicaTV, una WebTV automatizzata 24/7.
Il tuo compito è generare un palinsesto giornaliero DINAMICO e IMPREVEDIBILE in formato JSON.

REGOLE TASSATIVE:
1. L'output DEVE ESSERE ESCLUSIVAMENTE codice JSON valido, senza blocchi markdown (no ```json), senza preamboli né spiegazioni.
2. Le chiavi del JSON devono essere orari nel formato "HH:00" e coprire l'intera giornata in ordine cronologico.
3. Le ore di inizio devono includere sempre "00:00" e spaziare fino alle "22:00" o "23:00". Fai slot di 1 o 2 ore. Non saltare troppe ore.
4. I valori devono essere oggetti con due chiavi: "title" (titolo accattivante del programma) e "type" (categoria).

FORMAT DISPONIBILI (Usa solo questi in "type"):
- "news": Notiziario generale esteso
- "sport": Notiziario sportivo
- "meteo": Aggiornamento meteo
- "wellness": Rubrica su salute/benessere
- "podcast": Dialogo a due voci su un tema specifico
- "flash_60s": Bollettino rapidissimo di 60 secondi (usalo come pillola a orari sparsi per dare imprevedibilità)
- "music_only": Solo musica in background (utile di notte o in pausa pranzo)

LINEE GUIDA EDITORIALI PER IMPREVEDIBILITÀ:
- Varia i titoli. Invece di "Pranzo News", inventa "Oggi alle 13", "Newsica Live", "Ultim'ora Flash".
- Non mettere mai due "podcast" di fila.
- Spargi 3-4 slot "flash_60s" in momenti inaspettati (es. "11:00", "16:00", "23:00").
- Garantisci almeno un "meteo" al mattino e uno la sera.
- Rendi ogni giorno diverso dal precedente.

5. DEVI INCLUDERE OBBLIGATORIAMENTE i seguenti slot prefissati (Colonne Portanti e Appuntamenti Settimanali). Copiali esattamente e aggiungi il resto del palinsesto creativo attorno ad essi:
{fixed_slots_str}

Esempio di struttura richiesta:
{
  "00:00": {"title": "Night Vibes", "type": "music_only"},
  "07:00": {"title": "Buongiorno Newsica", "type": "news"},
  "09:00": {"title": "Tech in Pillole", "type": "flash_60s"}
}
"""

        user_prompt = f"Oggi è {date.today().isoformat()}. Genera il palinsesto creativo per oggi. Rispondi SOLO in JSON puro."

        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {"temperature": 0.8}
        }

        try:
            res = requests.post(self.ollama_url, json=payload, timeout=60)
            res.raise_for_status()
            response_text = res.json().get("response", "").strip()
            
            if res.status_code == 200:
                result = res.json().get("response", "")
                
                # Cerca un blocco JSON nella risposta
                start = result.find('{')
                end = result.rfind('}') + 1
                if start != -1 and end != -1:
                    result = result[start:end]
                    
                parsed_schedule = json.loads(result)
                # Verifica che tutte le chiavi fisse siano presenti
                for key, val in fixed_slots.items():
                    parsed_schedule[key] = val
                    
                # Riordina il dizionario per orario
                sorted_schedule = {k: parsed_schedule[k] for k in sorted(parsed_schedule.keys())}
                
                log_decision("EditorialDirector", f"Generato nuovo palinsesto dinamico per oggi con {len(sorted_schedule)} programmi.", level="SCHEDULING")
                return sorted_schedule
            
            logger.warning(f"Ollama ha restituito status {res.status_code}. Uso il fallback precalcolato.")
            log_decision("EditorialDirector", f"Fallback attivato: Ollama ha restituito status {res.status_code}", level="WARNING")
        except Exception as e:
            logger.error(f"❌ Errore durante la generazione LLM del palinsesto: {e}")
            log_decision("EditorialDirector", f"Fallback attivato: Errore di esecuzione: {e}", level="ERROR")
            
        return self.fallback_schedule

    def generate_music_prompt(self, time_of_day: str, fallback_prompt: str) -> str:
        logger.info(f"🧠 [EditorialDirectorAgent] Invenzione di un nuovo prompt musicale per {time_of_day}...")
        
        system_prompt = f"""Sei un abile produttore musicale e sound designer di NewsicaTV.
Il tuo compito è generare UN SOLO prompt testuale per un AI Music Generator (come ACE-Step).
Il brano deve essere STRUMENTALE, di ALTA QUALITÀ (clean production), senza rumori lo-fi o crackle, ed evocare l'orario del giorno: {time_of_day}.

REGOLE TASSATIVE:
1. L'output deve essere SOLO una stringa di tag separati da virgola. Nessun preambolo, nessuna spiegazione.
2. I tag devono essere in INGLESE.
3. Includi SEMPRE i tag: instrumental, clean production.
4. Non includere mai tag che sporcano l'audio (no lofi, no crackle, no distortion).
5. Usa massimo 10 tag pertinenti che descrivono il genere, il mood, e gli strumenti.

Esempio di output desiderato per "morning":
acoustic pop, bright acoustic guitar, light percussion, instrumental, optimistic, warm, clean production, morning

Inventa una combinazione nuova e interessante, diversa dall'esempio."""

        payload = {
            "model": self.model,
            "prompt": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.8
            }
        }
        
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=20)
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                if result:
                    logger.info(f"🎵 Prompt generato da Ollama: '{result}'")
                    log_decision("EditorialDirector", f"Inventato nuovo prompt per AI Music '{time_of_day}': {result}", level="MUSIC")
                    return result
            logger.warning(f"Ollama ha restituito status {response.status_code}, uso fallback.")
            log_decision("EditorialDirector", f"Errore generazione prompt AI Music (status {response.status_code}). Uso fallback.", level="WARNING")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ (Ollama) Errore nella generazione musicale: {e}. Uso fallback.")
            log_decision("EditorialDirector", f"Errore di rete generazione prompt AI Music. Uso fallback.", level="ERROR")
            
        return fallback_prompt


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = EditorialDirectorAgent()
    sched = agent.generate_dynamic_schedule()
    print(json.dumps(sched, indent=2))
