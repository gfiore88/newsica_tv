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
    "ansa_cronaca": "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml",
    "ansa_politica": "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
    "ansa_economia": "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    "ansa_cultura": "https://www.ansa.it/sito/notizie/cultura/cultura_rss.xml",
    "ansa_tecnologia": "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",
    "ansa_sport": "https://www.ansa.it/sito/notizie/sport/sport_rss.xml",
    "ansa_salute_benessere": "https://www.ansa.it/canale_saluteebenessere/notizie/saluteebenessere_rss.xml",
    "ansa_lifestyle": "https://www.ansa.it/canale_lifestyle/notizie/lifestyle_rss.xml",
    "sky_tg24": "https://tg24.sky.it/rss/tg24.xml",
}

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
RECENT_NEWS_FILE = os.path.join(TMP_DIR, "recent_news.json")
RECENT_WELLNESS_FILE = os.path.join(TMP_DIR, "recent_wellness.json")
WELLNESS_SOURCES = {"ansa_salute_benessere", "ansa_lifestyle"}
NEWS_SOURCES = {
    "ansa_ultimora",
    "ansa_mondo",
    "ansa_cronaca",
    "ansa_politica",
    "ansa_economia",
    "ansa_cultura",
    "ansa_tecnologia",
    "sky_tg24",
}
SPORT_SOURCES = {"ansa_sport"}
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
            "link": entry.link,
            "published": entry.get("published", "")
        })
        
    return news_items

def item_key(item):
    value = item.get("link") or item.get("title", "")
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()

def load_recent_news():
    try:
        with open(RECENT_NEWS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_recent_news(recent):
    compact = {group: keys[-160:] for group, keys in recent.items()}
    with open(RECENT_NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(compact, f, ensure_ascii=False, indent=2)

def normalized_title_key(item):
    title = item.get("title", "").lower()
    letters = [char if char.isalnum() else " " for char in title]
    words = [word for word in "".join(letters).split() if len(word) > 3]
    return " ".join(words[:8])

def title_tokens(item):
    title = item.get("title", "").lower()
    letters = [char if char.isalnum() else " " for char in title]
    stopwords = {
        "della", "delle", "degli", "dalla", "dalle", "alla", "alle",
        "sono", "come", "anche", "dopo", "prima", "oggi", "live",
        "diretta", "agli", "allo", "nella", "nelle", "sulla", "sulle",
    }
    return {
        word for word in "".join(letters).split()
        if len(word) > 3 and word not in stopwords
    }

def is_similar_story(item, selected):
    current_tokens = title_tokens(item)
    if not current_tokens:
        return False

    for existing in selected:
        existing_tokens = title_tokens(existing)
        if not existing_tokens:
            continue
        common = current_tokens & existing_tokens
        union = current_tokens | existing_tokens
        if len(common) >= 2 and len(common) / len(union) >= 0.25:
            return True
    return False

def select_rotating_items(items, group, limit, preferred_sources=None):
    recent = load_recent_news()
    recent_keys = set(recent.get(group, []))
    preferred_sources = preferred_sources or []
    selected = []
    selected_title_keys = set()

    def add_item(item):
        key = item_key(item)
        title_key = normalized_title_key(item)
        if key in {item_key(existing) for existing in selected}:
            return False
        if title_key and title_key in selected_title_keys:
            return False
        if is_similar_story(item, selected):
            return False
        selected.append(item)
        if title_key:
            selected_title_keys.add(title_key)
        return True

    def candidates_for(source=None, fresh_only=True):
        candidates = items
        if source:
            candidates = [item for item in candidates if item.get("source") == source]
        if fresh_only:
            candidates = [item for item in candidates if item_key(item) not in recent_keys]
        return candidates

    for source in preferred_sources:
        for item in candidates_for(source, fresh_only=True):
            if add_item(item):
                break

    source_order = preferred_sources + [
        source for source in sorted({item.get("source") for item in items})
        if source not in preferred_sources
    ]
    for fresh_only in (True, False):
        made_progress = True
        while len(selected) < limit and made_progress:
            made_progress = False
            for source in source_order:
                for item in candidates_for(source, fresh_only=fresh_only):
                    if add_item(item):
                        made_progress = True
                        break
                if len(selected) >= limit:
                    break
        if len(selected) >= limit:
            break

    recent[group] = recent.get(group, []) + [item_key(item) for item in selected]
    save_recent_news(recent)
    return selected[:limit]

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

WEATHER_CODES = {
    0: "cielo sereno, soleggiato",
    1: "prevalentemente sereno",
    2: "parzialmente nuvoloso",
    3: "coperto, cielo nuvoloso",
    45: "presenza di nebbia", 48: "nebbia con deposito di galaverna",
    51: "pioggerella leggera", 53: "pioggerella moderata", 55: "pioggerella fitta",
    61: "pioggia debole", 63: "pioggia moderata", 65: "pioggia forte",
    71: "nevicata debole", 73: "nevicata moderata", 75: "nevicata forte",
    80: "acquazzoni deboli", 81: "acquazzoni moderati", 82: "acquazzoni violenti",
    95: "temporale debole o moderato", 96: "temporale con grandine debole", 99: "temporale con forte grandine"
}

def fetch_weather():
    """
    Recupera i dati meteo per Nord (Milano), Centro (Roma) e Sud (Napoli) tramite Open-Meteo API.
    """
    cities = {
        "nord": {"name": "Milano", "lat": 45.4642, "lon": 9.1900},
        "centro": {"name": "Roma", "lat": 41.8902, "lon": 12.4922},
        "sud": {"name": "Napoli", "lat": 40.8518, "lon": 14.2681}
    }
    
    results = {}
    for key, city in cities.items():
        url = f"https://api.open-meteo.com/v1/forecast?latitude={city['lat']}&longitude={city['lon']}&current_weather=true"
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            current = data.get("current_weather", {})
            code = current.get("weathercode", 0)
            desc = WEATHER_CODES.get(code, "variabile")
            results[key] = {
                "citta": city["name"],
                "temperatura": current.get("temperature"),
                "vento": current.get("windspeed"),
                "condizioni": desc
            }
        except Exception as e:
            print(f"⚠️ Errore recupero meteo per {city['name']}: {e}")
            results[key] = {"citta": city["name"], "condizioni": "dati temporaneamente non disponibili"}
            
    summary_text = (
        f"Nord Italia - Milano: {results['nord']['condizioni']}, temperatura {results['nord'].get('temperatura', 'N/D')}°C. "
        f"Centro Italia - Roma: {results['centro']['condizioni']}, temperatura {results['centro'].get('temperatura', 'N/D')}°C. "
        f"Sud e Isole - Napoli: {results['sud']['condizioni']}, temperatura {results['sud'].get('temperatura', 'N/D')}°C."
    )
    
    return {
        "title": "Meteo Italia",
        "summary": summary_text,
        "link": "https://open-meteo.com",
        "source": "meteo"
    }

def main():
    print(f"[{datetime.now()}] Avvio scraping delle news...")
    
    # Assicuriamoci che la cartella tmp esista
    os.makedirs(TMP_DIR, exist_ok=True)
    
    all_news = []
    news_pool = []
    sport_pool = []
    
    # 1. Preleva le ultime notizie dai feed RSS
    wellness_pool = []
    for category, url in RSS_FEEDS.items():
        print(f"Recupero {category}...")
        news = fetch_latest_news(url, max_items=12 if category in NEWS_SOURCES else 8)
        for item in news:
            item['source'] = category
        if category in WELLNESS_SOURCES:
            wellness_pool.extend(news)
        elif category in SPORT_SOURCES:
            sport_pool.extend(news)
        elif category in NEWS_SOURCES:
            news_pool.extend(news)
        else:
            all_news.extend(news)

    all_news.extend(select_rotating_items(
        news_pool,
        "news",
        limit=6,
        preferred_sources=["ansa_ultimora", "ansa_mondo", "sky_tg24"]
    ))
    all_news.extend(select_rotating_items(
        sport_pool,
        "sport",
        limit=3,
        preferred_sources=["ansa_sport"]
    ))

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
        
    print(f"[{datetime.now()}] Scraping completato. Salvate {len(all_news)} notizie in {output_file}")

if __name__ == "__main__":
    main()
