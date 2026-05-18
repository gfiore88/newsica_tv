import feedparser
import json
import os
from datetime import datetime

# Fonti RSS gratuite
RSS_FEEDS = {
    "ansa_ultimora": "https://www.ansa.it/sito/ansait_rss.xml",
    "ansa_mondo": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml"
}

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")

def fetch_latest_news(feed_url, max_items=3):
    """
    Scarica le ultime notizie da un feed RSS.
    Restituisce una lista di dizionari con 'title', 'summary' e 'link'.
    """
    parsed_feed = feedparser.parse(feed_url)
    news_items = []
    
    for entry in parsed_feed.entries[:max_items]:
        news_items.append({
            "title": entry.title,
            "summary": entry.get('description', ''),
            "link": entry.link
        })
        
    return news_items

def main():
    print(f"[{datetime.now()}] Avvio scraping delle news...")
    
    # Assicuriamoci che la cartella tmp esista
    os.makedirs(TMP_DIR, exist_ok=True)
    
    all_news = []
    
    # Preleva le ultime 2 notizie da ogni feed
    for category, url in RSS_FEEDS.items():
        print(f"Recupero {category}...")
        news = fetch_latest_news(url, max_items=2)
        for item in news:
            item['source'] = category
        all_news.extend(news)
        
    output_file = os.path.join(TMP_DIR, "raw_news.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_news, f, ensure_ascii=False, indent=4)
        
    # Salva il file per il ticker scorrevole (solo i titoli)
    ticker_file = os.path.join(TMP_DIR, "ticker.txt")
    ticker_testo = "   |   ".join([f"[{news['source'].replace('ansa_', '').upper()}] {news['title'].replace('%', ' percento')}" for news in all_news]) + "   |   "
    with open(ticker_file, 'w', encoding='utf-8') as f:
        f.write(ticker_testo)
        
    print(f"[{datetime.now()}] Scraping completato. Salvate {len(all_news)} notizie in {output_file}")
    print(f"[{datetime.now()}] Ticker generato in {ticker_file}")

if __name__ == "__main__":
    main()
