import feedparser
import json
import os
from datetime import datetime
import requests
import hashlib

# Fonti RSS gratuite
RSS_FEEDS = {
    "ansa_ultimora": "https://www.ansa.it/sito/ansait_rss.xml",
    "ansa_mondo": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml",
    "ansa_sport": "https://www.ansa.it/sito/notizie/sport/sport_rss.xml",
    "ansa_salute_benessere": "https://www.ansa.it/canale_saluteebenessere/notizie/saluteebenessere_rss.xml",
    "ansa_lifestyle": "https://www.ansa.it/canale_lifestyle/notizie/lifestyle_rss.xml"
}

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
RECENT_WELLNESS_FILE = os.path.join(TMP_DIR, "recent_wellness.json")
WELLNESS_SOURCES = {"ansa_salute_benessere", "ansa_lifestyle"}
WELLNESS_KEYWORDS = (
    "fitness", "allenamento", "sport", "cammin", "corsa", "palestra",
    "benessere", "salute", "sonno", "stress", "aliment", "nutriz",
    "cura", "pelle", "corpo", "mente", "emozion", "prevenzione",
    "abitudine", "fiori", "stelle", "viaggio", "estate"
)
WELLNESS_PENALTY_KEYWORDS = (
    "sciopero", "ebola", "vittime", "morto", "ricovero", "condanna",
    "emergenza", "tagliati", "diabete", "farmaci", "allergia", "epidemia"
)
WELLNESS_TIPS = (
    {
        "title": "La camminata breve che rimette in moto la giornata",
        "summary": "Anche dieci minuti a passo tranquillo aiutano a staccare dagli schermi e a rientrare con piu' energia.",
        "link": "local://wellness/camminata-breve",
        "source": "wellness_tip"
    },
    {
        "title": "Una routine serale semplice per dormire meglio",
        "summary": "Luci piu' basse, telefono lontano e qualche minuto di lettura possono diventare un piccolo rito quotidiano.",
        "link": "local://wellness/routine-serale",
        "source": "wellness_tip"
    },
    {
        "title": "Colazione senza fretta, il primo gesto di cura",
        "summary": "Preparare qualcosa di semplice e sedersi davvero a mangiarlo cambia il ritmo con cui si entra nella giornata.",
        "link": "local://wellness/colazione-lenta",
        "source": "wellness_tip"
    },
    {
        "title": "Stretching da scrivania, pochi movimenti fanno respirare il corpo",
        "summary": "Spalle, collo e schiena ringraziano quando ogni tanto ci si alza e si sciolgono le tensioni accumulate.",
        "link": "local://wellness/stretching-scrivania",
        "source": "wellness_tip"
    },
    {
        "title": "La borraccia sulla scrivania come promemoria gentile",
        "summary": "Bere con regolarita' diventa piu' facile quando l'acqua e' visibile e a portata di mano.",
        "link": "local://wellness/borraccia",
        "source": "wellness_tip"
    }
)

def fetch_latest_news(feed_url, max_items=3):
    """
    Scarica le ultime notizie da un feed RSS.
    Restituisce una lista di dizionari con 'title', 'summary' e 'link'.
    """
    try:
        response = requests.get(feed_url, timeout=8)
        response.raise_for_status()
    except Exception as e:
        print(f"⚠️ Errore recupero feed {feed_url}: {e}")
        return []

    parsed_feed = feedparser.parse(response.content)
    news_items = []
    
    for entry in parsed_feed.entries[:max_items]:
        news_items.append({
            "title": entry.title,
            "summary": entry.get('description', ''),
            "link": entry.link
        })
        
    return news_items

def item_key(item):
    value = item.get("link") or item.get("title", "")
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()

def load_recent_wellness():
    try:
        with open(RECENT_WELLNESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_recent_wellness(keys):
    with open(RECENT_WELLNESS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys[-60:], f, ensure_ascii=False, indent=2)

def wellness_score(item):
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    score = sum(1 for keyword in WELLNESS_KEYWORDS if keyword in text)
    score -= 3 * sum(1 for keyword in WELLNESS_PENALTY_KEYWORDS if keyword in text)
    if item.get("source") == "ansa_lifestyle":
        score += 4
    if item.get("source") == "wellness_tip":
        score += 3
    return score

def select_fresh_wellness(items, limit=3):
    recent = load_recent_wellness()
    ranked = sorted(items, key=wellness_score, reverse=True)
    light_items = [
        item for item in ranked
        if item.get("source") in {"wellness_tip", "ansa_lifestyle"} or wellness_score(item) >= 2
    ]
    fresh = [item for item in light_items if item_key(item) not in recent]
    candidates = fresh or light_items or ranked
    selected = []

    for preferred_source in ("wellness_tip", "ansa_lifestyle"):
        preferred_candidates = [item for item in candidates if item.get("source") == preferred_source]
        if not preferred_candidates:
            preferred_candidates = [item for item in light_items if item.get("source") == preferred_source]
        for item in preferred_candidates:
            if item.get("source") == preferred_source and item not in selected:
                selected.append(item)
                break

    for item in candidates:
        if item not in selected:
            selected.append(item)
        if len(selected) >= limit:
            break

    save_recent_wellness(recent + [item_key(item) for item in selected])
    return selected

def fetch_weather():
    """
    Recupera i dati meteo attuali per Roma tramite l'API gratuita Open-Meteo.
    """
    url = "https://api.open-meteo.com/v1/forecast?latitude=41.89&longitude=12.51&current_weather=true"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        current = data.get("current_weather", {})
        return {
            "title": "Meteo Roma",
            "summary": f"Temperatura: {current.get('temperature')}°C, Vento: {current.get('windspeed')} km/h, Codice: {current.get('weathercode')}",
            "link": "https://open-meteo.com",
            "source": "meteo"
        }
    except Exception as e:
        print(f"⚠️ Errore recupero meteo: {e}")
        return None

def main():
    print(f"[{datetime.now()}] Avvio scraping delle news...")
    
    # Assicuriamoci che la cartella tmp esista
    os.makedirs(TMP_DIR, exist_ok=True)
    
    all_news = []
    
    # 1. Preleva le ultime notizie dai feed RSS
    wellness_pool = []
    for category, url in RSS_FEEDS.items():
        print(f"Recupero {category}...")
        news = fetch_latest_news(url, max_items=8 if category in WELLNESS_SOURCES else 2)
        for item in news:
            item['source'] = category
        if category in WELLNESS_SOURCES:
            wellness_pool.extend(news)
        else:
            all_news.extend(news)

    wellness_pool.extend(WELLNESS_TIPS)
    if wellness_pool:
        all_news.extend(select_fresh_wellness(wellness_pool, limit=3))
        
    # 2. Recupera il meteo
    print("Recupero dati meteo...")
    weather = fetch_weather()
    if weather:
        all_news.append(weather)
        
    output_file = os.path.join(TMP_DIR, "raw_news.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_news, f, ensure_ascii=False, indent=4)
        
    # Salva il file per il ticker scorrevole (solo i titoli)
    ticker_file = os.path.join(TMP_DIR, "ticker.txt")
    ticker_testo = "   |   ".join([f"[{news['source'].upper()}] {news['title'].replace('%', ' percento')}" for news in all_news]) + "   |   "
    with open(ticker_file, 'w', encoding='utf-8') as f:
        f.write(ticker_testo)
        
    print(f"[{datetime.now()}] Scraping completato. Salvate {len(all_news)} notizie in {output_file}")
    print(f"[{datetime.now()}] Ticker generato in {ticker_file}")

if __name__ == "__main__":
    main()
