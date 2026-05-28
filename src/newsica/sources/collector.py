from newsica.config.paths import TMP_DIR
from newsica.sources.loader import load_sources_registry
from newsica.sources.rotation import select_rotating_items
from newsica.sources.rss import fetch_latest_news
from newsica.sources.weather import fetch_weather
from newsica.sources.wellness import select_fresh_wellness

RECENT_NEWS_FILE = TMP_DIR / "recent_news.json"
RECENT_WELLNESS_FILE = TMP_DIR / "recent_wellness.json"


def collect_news_items():
    registry = load_sources_registry()
    all_news = []
    news_pool = []
    sport_pool = []
    wellness_pool = []
    motori_pool = []

    for source_id, entry in registry["feeds"].items():
        url = entry["url"]
        print(f"Recupero {source_id}...")
        max_items = 12 if source_id in registry["news_sources"] else 8
        news = fetch_latest_news(url, max_items=max_items)
        for item in news:
            item["source"] = source_id
        if source_id in registry["wellness_sources"]:
            wellness_pool.extend(news)
        elif source_id in registry["sport_sources"]:
            sport_pool.extend(news)
        elif source_id in registry["motori_sources"]:
            motori_pool.extend(news)
        elif source_id in registry["news_sources"]:
            news_pool.extend(news)
        else:
            all_news.extend(news)

    all_news.extend(select_rotating_items(
        news_pool,
        "news",
        limit=registry["news_rotation_limit"],
        recent_file=RECENT_NEWS_FILE,
        preferred_sources=registry["news_preferred_sources"],
    ))
    all_news.extend(select_rotating_items(
        sport_pool,
        "sport",
        limit=registry["sport_rotation_limit"],
        recent_file=RECENT_NEWS_FILE,
        preferred_sources=registry["sport_preferred_sources"],
    ))
    all_news.extend(select_rotating_items(
        motori_pool,
        "motori",
        limit=registry["motori_rotation_limit"],
        recent_file=RECENT_NEWS_FILE,
        preferred_sources=registry["motori_preferred_sources"],
    ))

    if wellness_pool:
        all_news.extend(select_fresh_wellness(wellness_pool, RECENT_WELLNESS_FILE, limit=3))

    print("Recupero dati meteo...")
    weather = fetch_weather()
    if weather:
        all_news.append(weather)

    return all_news
