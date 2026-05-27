import feedparser
import requests


def fetch_latest_news(feed_url, max_items=3):
    try:
        response = requests.get(feed_url, timeout=8)
        response.raise_for_status()
    except Exception as e:
        print(f"⚠️ Errore recupero feed {feed_url}: {e}")
        return []

    parsed_feed = feedparser.parse(response.content)
    news_items = []

    for entry in parsed_feed.entries[:max_items]:
        img_url = ""
        if hasattr(entry, "media_content") and entry.media_content:
            img_url = entry.media_content[0].get("url", "")
        if not img_url and hasattr(entry, "links"):
            for link in entry.links:
                if link.get("rel") == "enclosure" and "image" in link.get("type", ""):
                    img_url = link.get("href")
                    break
                    
        news_items.append({
            "title": entry.title,
            "summary": entry.get("description", ""),
            "link": entry.link,
            "published": entry.get("published", ""),
            "image_url": img_url,
        })

    return news_items

