import os
import json
import logging
import requests
from datetime import date

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
            
            # Pulizia per sicurezza (spesso l'LLM mette markdown nonostante i divieti)
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            schedule = json.loads(response_text)
            
            # Validazione minima
            if "00:00" not in schedule:
                schedule["00:00"] = {"title": "Night Vibes", "type": "music_only"}
            
            # Sovrascrittura sicura delle colonne portanti
            for k, v in fixed_slots.items():
                schedule[k] = v
            
            # Ordina le chiavi
            sorted_schedule = {k: schedule[k] for k in sorted(schedule.keys())}
            logger.info("✅ Palinsesto dinamico generato con successo dall'IA!")
            return sorted_schedule

        except Exception as e:
            logger.error(f"❌ Errore durante la generazione LLM del palinsesto: {e}")
            logger.info("⚠️ Uso il palinsesto di fallback precalcolato.")
            return self.fallback_schedule

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = EditorialDirectorAgent()
    sched = agent.generate_dynamic_schedule()
    print(json.dumps(sched, indent=2))
