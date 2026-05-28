RSS_FEED_DEFINITIONS = {
    "ansa_cronaca": {"url": "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml", "category": "news"},
    "ansa_cultura": {"url": "https://www.ansa.it/sito/notizie/cultura/cultura_rss.xml", "category": "cultura"},
    "ansa_economia": {"url": "https://www.ansa.it/sito/notizie/economia/economia_rss.xml", "category": "economia"},
    "ansa_lifestyle": {"url": "https://www.ansa.it/canale_lifestyle/notizie/lifestyle_rss.xml", "category": "wellness"},
    "ansa_mondo": {"url": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml", "category": "news"},
    "ansa_motori": {"url": "https://www.ansa.it/canale_motori/notizie/motori_rss.xml", "category": "motori"},
    "ansa_politica": {"url": "https://www.ansa.it/sito/notizie/politica/politica_rss.xml", "category": "news"},
    "ansa_salute_benessere": {"url": "https://www.ansa.it/canale_saluteebenessere/notizie/saluteebenessere_rss.xml", "category": "wellness"},
    "ansa_sport": {"url": "https://www.ansa.it/sito/notizie/sport/sport_rss.xml", "category": "sport"},
    "ansa_tecnologia": {"url": "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml", "category": "tech"},
    "ansa_ultimora": {"url": "https://www.ansa.it/sito/ansait_rss.xml", "category": "breaking"},
    "agi_cronaca": {"url": "https://www.agi.it/cronaca/rss", "category": "news"},
    "agi_cultura": {"url": "https://www.agi.it/cultura/rss", "category": "cultura"},
    "agi_economia": {"url": "https://www.agi.it/economia/rss", "category": "economia"},
    "agi_estero": {"url": "https://www.agi.it/estero/rss", "category": "news"},
    "agi_innovazione": {"url": "https://www.agi.it/innovazione/rss", "category": "tech"},
    "agi_politica": {"url": "https://www.agi.it/politica/rss", "category": "news"},
    "agi_sport": {"url": "https://www.agi.it/sport/rss", "category": "sport"},
    "sky_tg24": {"url": "https://tg24.sky.it/rss/tg24.xml", "category": "news"},
}

GENERAL_NEWS_CATEGORIES = {"breaking", "cultura", "economia", "general", "news", "tech"}

RSS_FEEDS = {
    feed_id: entry["url"]
    for feed_id, entry in RSS_FEED_DEFINITIONS.items()
}

NEWS_SOURCES = {
    feed_id
    for feed_id, entry in RSS_FEED_DEFINITIONS.items()
    if entry.get("category", "news") in GENERAL_NEWS_CATEGORIES
}

SPORT_SOURCES = {
    feed_id
    for feed_id, entry in RSS_FEED_DEFINITIONS.items()
    if entry.get("category") == "sport"
}

WELLNESS_SOURCES = {
    feed_id
    for feed_id, entry in RSS_FEED_DEFINITIONS.items()
    if entry.get("category") == "wellness"
}

MOTORI_SOURCES = {
    feed_id
    for feed_id, entry in RSS_FEED_DEFINITIONS.items()
    if entry.get("category") == "motori"
}

NEWS_PREFERRED_SOURCES = [
    "ansa_ultimora",
    "ansa_cronaca",
    "ansa_politica",
    "ansa_mondo",
    "agi_cronaca",
    "agi_politica",
    "agi_estero",
    "sky_tg24",
]

SPORT_PREFERRED_SOURCES = ["ansa_sport", "agi_sport"]
WELLNESS_PREFERRED_SOURCES = ("ansa_lifestyle", "ansa_salute_benessere")
MOTORI_PREFERRED_SOURCES = ["ansa_motori"]

NEWS_ROTATION_LIMIT = 10
SPORT_ROTATION_LIMIT = 4
MOTORI_ROTATION_LIMIT = 4


def max_items_for_source(source):
    return 12 if source in NEWS_SOURCES else 8
