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
    "ansa_motori": "https://www.ansa.it/canale_motori/notizie/motori_rss.xml",
    "sky_tg24": "https://tg24.sky.it/rss/tg24.xml",
    "agi_cronaca": "https://www.agi.it/cronaca/rss",
    "agi_politica": "https://www.agi.it/politica/rss",
    "agi_estero": "https://www.agi.it/estero/rss",
    "agi_economia": "https://www.agi.it/economia/rss",
    "agi_innovazione": "https://www.agi.it/innovazione/rss",
    "agi_cultura": "https://www.agi.it/cultura/rss",
    "agi_sport": "https://www.agi.it/sport/rss",
}

NEWS_SOURCES = {
    "ansa_ultimora",
    "ansa_mondo",
    "ansa_cronaca",
    "ansa_politica",
    "ansa_economia",
    "ansa_cultura",
    "ansa_tecnologia",
    "sky_tg24",
    "agi_cronaca",
    "agi_politica",
    "agi_estero",
    "agi_economia",
    "agi_innovazione",
    "agi_cultura",
}

SPORT_SOURCES = {"ansa_sport", "agi_sport"}
WELLNESS_SOURCES = {"ansa_salute_benessere", "ansa_lifestyle"}
MOTORI_SOURCES = {"ansa_motori"}

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
