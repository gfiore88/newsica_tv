import os
import time
import json
import random
from datetime import datetime
_singleton_lock = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TICKER_FILE = os.path.join(TMP_DIR, "ticker.txt")
RAW_NEWS_FILE = os.path.join(TMP_DIR, "raw_news.json")
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
            
            # Tenta di caricare le notizie reali scrapate di recente
            flash_text = ""
            if os.path.exists(RAW_NEWS_FILE):
                try:
                    with open(RAW_NEWS_FILE, "r", encoding="utf-8") as f:
                        all_news = json.load(f)
                    if all_news:
                        # Seleziona fino a 4 notizie reali a caso
                        sampled_news = random.sample(all_news, min(4, len(all_news)))
                        items = []
                        for news in sampled_news:
                            source = news.get("source", "NEWS").upper()
                            title = news.get("title", "").replace("%", " percento")
                            if title:
                                items.append(f"[{source}] {title}")
                        flash_text = "   •   ".join(items)
                except Exception as e:
                    print(f"⚠️ Errore caricamento notizie per ticker: {e}")
            
            # Fallback se le notizie reali non sono ancora disponibili o c'è un errore
            if not flash_text:
                flashes = random.sample(FLASH_NEWS, 3)
                flash_text = "   •   ".join(flashes)
            
            # Stringa ticker con spazi alla fine per un loop fluido
            ticker_content = f"        NEWSICATV - WEB TV H24   •   {date_str} {time_str}   •   {status_text}   •   FLASH: {flash_text}   •   {next_block}                                                 "
            
            with open(TICKER_FILE + ".tmp", "w") as f:
                f.write(ticker_content)
            os.replace(TICKER_FILE + ".tmp", TICKER_FILE)
            
        except Exception as e:
            print(f"⚠️ Errore Ticker Agent: {e}")
            
        time.sleep(15)

def check_singleton(name):
    import fcntl
    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")
    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        global _singleton_lock
        _singleton_lock = f
        f.write(str(os.getpid()))
        f.flush()
        return True
    except (IOError, OSError):
        print(f"❌ ERRORE: Un'altra istanza di {name} è già in esecuzione!")
        return False

if __name__ == "__main__":
    import sys
    if not check_singleton("ticker_agent"):
        print("❌ Uscita immediata per prevenire conflitti.")
        sys.exit(1)
    update_ticker()
