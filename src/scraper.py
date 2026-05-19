import json
import sys
import time
from datetime import datetime

from newsica.config.paths import TMP_DIR
from newsica.sources.collector import collect_news_items

OUTPUT_FILE = TMP_DIR / "raw_news.json"
CACHE_SECONDS = 900


def should_use_cache(force_fetch):
    if force_fetch or not OUTPUT_FILE.exists():
        return False
    age = time.time() - OUTPUT_FILE.stat().st_mtime
    if age < CACHE_SECONDS:
        print(f"[{datetime.now()}] Cache valida ({int(age)}s di età). Salto lo scraping di rete.")
        return True
    return False


def main():
    force_fetch = "--force" in sys.argv
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if should_use_cache(force_fetch):
        return

    print(f"[{datetime.now()}] Avvio scraping delle news...")
    all_news = collect_news_items()
    OUTPUT_FILE.write_text(json.dumps(all_news, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"[{datetime.now()}] Scraping completato. Salvate {len(all_news)} notizie in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
