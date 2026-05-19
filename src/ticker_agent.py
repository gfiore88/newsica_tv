import os
import time
import json
import random
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TICKER_FILE = os.path.join(TMP_DIR, "ticker.txt")
STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")

FLASH_NEWS = [
    "MERCATI: Borsa in rialzo dopo le decisioni della BCE",
    "TECNOLOGIA: L'Intelligenza Artificiale fa passi da gigante nel 2026",
    "METEO: Temperature sopra la media stagionale nel weekend",
    "SPORT: Grande attesa per il match di stasera",
    "CULTURA: Record di visite nei musei italiani in questo mese",
    "CRONACA: Nuove scoperte archeologiche nel cuore di Roma"
]

def update_ticker():
    print("📡 Ticker Agent avviato. Generazione testo scorrevole in background...")
    
    while True:
        try:
            status_text = "Benvenuti su Newsica TV"
            next_block = ""
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                
                if state.get("current_block") == "breaking_news":
                    status_text = "🚨 EDIZIONE STRAORDINARIA IN CORSO"
                elif state.get("current_title"):
                    status_text = f"In onda: {state.get('current_title').upper()}"
                
                if state.get("next_block"):
                    next_block = f"Tra poco: {state.get('next_block').upper()}"
                    
            now = datetime.now()
            time_str = now.strftime("%H:%M")
            date_str = now.strftime("%d/%m/%Y")
            
            flash = random.choice(FLASH_NEWS)
            
            # Stringa ticker. Tanti spazi per far staccare bene il loop
            ticker_content = f"        NEWSICATV - WEB TV H24   •   {date_str} {time_str}   •   {status_text}   •   FLASH: {flash}   •   {next_block}        "
            
            with open(TICKER_FILE + ".tmp", "w") as f:
                f.write(ticker_content)
            os.replace(TICKER_FILE + ".tmp", TICKER_FILE)
            
        except Exception as e:
            print(f"⚠️ Errore Ticker Agent: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    update_ticker()
