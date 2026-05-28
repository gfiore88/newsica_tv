from newsica.config.paths import TMP_DIR
from newsica.sources.registry import (
    NEWS_PREFERRED_SOURCES,
    NEWS_ROTATION_LIMIT,
    NEWS_SOURCES,
    RSS_FEEDS,
    SPORT_PREFERRED_SOURCES,
    SPORT_ROTATION_LIMIT,
    SPORT_SOURCES,
    WELLNESS_SOURCES,
    MOTORI_PREFERRED_SOURCES,
    MOTORI_ROTATION_LIMIT,
    MOTORI_SOURCES,
    max_items_for_source,
)
from newsica.sources.rotation import select_rotating_items
from newsica.sources.rss import fetch_latest_news
from newsica.sources.weather import fetch_weather
from newsica.sources.wellness import select_fresh_wellness

RECENT_NEWS_FILE = TMP_DIR / "recent_news.json"
RECENT_WELLNESS_FILE = TMP_DIR / "recent_wellness.json"


def collect_news_items():
    all_news = []
    news_pool = []
    sport_pool = []
    wellness_pool = []
    motori_pool = []

    for category, url in RSS_FEEDS.items():
        print(f"Recupero {category}...")
        news = fetch_latest_news(url, max_items=max_items_for_source(category))
        for item in news:
            item["source"] = category
        if category in WELLNESS_SOURCES:
            wellness_pool.extend(news)
        elif category in SPORT_SOURCES:
            sport_pool.extend(news)
        elif category in MOTORI_SOURCES:
            motori_pool.extend(news)
        elif category in NEWS_SOURCES:
            news_pool.extend(news)
        else:
            all_news.extend(news)

    all_news.extend(select_rotating_items(
        news_pool,
        "news",
        limit=NEWS_ROTATION_LIMIT,
        recent_file=RECENT_NEWS_FILE,
        preferred_sources=NEWS_PREFERRED_SOURCES,
    ))
    all_news.extend(select_rotating_items(
        sport_pool,
        "sport",
        limit=SPORT_ROTATION_LIMIT,
        recent_file=RECENT_NEWS_FILE,
        preferred_sources=SPORT_PREFERRED_SOURCES,
    ))
    all_news.extend(select_rotating_items(
        motori_pool,
        "motori",
        limit=MOTORI_ROTATION_LIMIT,
        recent_file=RECENT_NEWS_FILE,
        preferred_sources=MOTORI_PREFERRED_SOURCES,
    ))

    if wellness_pool:
        all_news.extend(select_fresh_wellness(wellness_pool, RECENT_WELLNESS_FILE, limit=3))

    print("Recupero dati meteo...")
    weather = fetch_weather()
    if weather:
        all_news.append(weather)

    return all_news
