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
WELLNESS_SOURCES = {"ansa_salute_benessere", "ansa_lifestyle"}

NEWS_PREFERRED_SOURCES = ["ansa_ultimora", "ansa_mondo", "sky_tg24"]
SPORT_PREFERRED_SOURCES = ["ansa_sport"]
WELLNESS_PREFERRED_SOURCES = ("ansa_lifestyle", "ansa_salute_benessere")


def max_items_for_source(source):
    return 12 if source in NEWS_SOURCES else 8

