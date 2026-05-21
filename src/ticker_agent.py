import os
import time
import json
from datetime import datetime

_singleton_lock = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TICKER_FILE = os.path.join(TMP_DIR, "ticker.txt")
RAW_NEWS_FILE = os.path.join(TMP_DIR, "raw_news.json")
STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")

FLASH_NEWS = [
    "MERCATI: Borsa in rialzo dopo le decisioni della BCE",
    "TECNOLOGIA: L'Intelligenza Artificiale fa passi da gigante nel 2026",
    "METEO: Temperature sopra la media stagionale nel weekend",
    "SPORT: Grande attesa per il match di stasera",
    "CULTURA: Record di visite nei musei italiani in questo mese",
    "CRONACA: Nuove scoperte archeologiche nel cuore di Roma",
]

SCHEDULE_TYPE_LABELS = {
    "flash_60s": "Flash",
    "podcast": "Podcast",
    "sport": "Sport",
    "news": "News",
    "meteo": "Meteo",
    "wellness": "Benessere",
    "music_only": "Musica",
}


def clean_text(text):
    return " ".join((text or "").replace("%", " percento").split())


def clean_schedule_title(block, max_chars=42):
    block_type = block.get("type", "")
    label = SCHEDULE_TYPE_LABELS.get(block_type)
    title = (block.get("title") or label or "").strip()

    if block_type == "flash_60s":
        compact = "Flash News"
    elif block_type in {"sport", "news", "meteo", "wellness", "music_only"} and label:
        compact = label
    elif block_type == "podcast":
        topic = title.split(":", 1)[1].strip() if ":" in title else title
        compact = f"Podcast: {topic}" if topic else "Podcast"
    elif label:
        compact = f"{label}: {title}" if title and title.lower() != label.lower() else label
    else:
        compact = title

    compact = clean_text(compact)

    # Limite solo di sicurezza: il wrap vero lo fa overlay_agent.py.
    if len(compact) > max_chars:
        compact = compact[: max_chars - 1].rstrip() + "…"

    return compact


def build_minimal_ticker(status_text, flash_text, next_block):
    parts = []

    if status_text:
        parts.append(clean_text(status_text))

    if flash_text:
        parts.append(clean_text(flash_text))

    if next_block:
        parts.append(clean_text(next_block))

    # Spazi iniziali/finali contenuti: evita ticker troppo "gonfio".
    return "   " + "  •  ".join(parts) + "   "


def update_ticker():
    print("📡 Ticker Agent avviato. Generazione testo scorrevole in background...")

    last_ticker_content = ""

    while True:
        try:
            status_text = "NewsicaTV"
            next_block = ""

            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)

                if (
                    state.get("current_block")
                    in {"breaking_news", "trasmissione_straordinaria"}
                    or state.get("status") == "SPECIAL_BROADCAST"
                ):
                    status_text = "🚨 Edizione straordinaria"
                elif state.get("current_title"):
                    status_text = f"In onda: {state.get('current_title')}"

                if state.get("next_block"):
                    next_block = f"Tra poco: {state.get('next_block')}"

            now = datetime.now()
            time_str = now.strftime("%H:%M")
            date_str = now.strftime("%d/%m/%Y")

            clock_file = os.path.join(TMP_DIR, "clock.txt")
            date_file = os.path.join(TMP_DIR, "date.txt")

            with open(clock_file + ".tmp", "w", encoding="utf-8") as f:
                f.write(time_str)
            os.replace(clock_file + ".tmp", clock_file)

            with open(date_file + ".tmp", "w", encoding="utf-8") as f:
                f.write(date_str)
            os.replace(date_file + ".tmp", date_file)

            flash_text = ""

            if os.path.exists(RAW_NEWS_FILE):
                try:
                    with open(RAW_NEWS_FILE, "r", encoding="utf-8") as f:
                        all_news = json.load(f)

                    if all_news:
                        stable_news = all_news[:6]
                        items = []

                        for news in stable_news:
                            source = clean_text(news.get("source", "NEWS")).upper()
                            title = clean_text(news.get("title", ""))

                            if title:
                                items.append(f"[{source}] {title}")

                        flash_text = "  •  ".join(items)
                except Exception as e:
                    print(f"⚠️ Errore caricamento notizie per ticker: {e}")

            if not flash_text:
                stable_flashes = [clean_text(item) for item in FLASH_NEWS[:4]]
                flash_text = "  •  ".join(stable_flashes)

            ticker_content = build_minimal_ticker(
                status_text=status_text,
                flash_text=flash_text,
                next_block=next_block,
            )

            if ticker_content != last_ticker_content:
                with open(TICKER_FILE + ".tmp", "w", encoding="utf-8") as f:
                    f.write(ticker_content)
                os.replace(TICKER_FILE + ".tmp", TICKER_FILE)
                last_ticker_content = ticker_content

            # --- Prossimi eventi timeline overlay ---
            schedule_next_file = os.path.join(TMP_DIR, "schedule_next.txt")

            try:
                import sys as _sys

                src_dir = os.path.dirname(os.path.abspath(__file__))

                if src_dir not in _sys.path:
                    _sys.path.insert(0, src_dir)

                from schedule_generator import get_current_schedule

                schedule_data = get_current_schedule()
                times = sorted(schedule_data.keys())
                now_str = datetime.now().strftime("%H:%M")

                current_key = times[0]

                for t in times:
                    if t <= now_str:
                        current_key = t
                    else:
                        break

                current_idx = times.index(current_key)

                next_slots = []

                for i in range(1, 5):
                    idx = (current_idx + i) % len(times)
                    t = times[idx]
                    block = schedule_data[t]
                    title = clean_schedule_title(block)
                    next_slots.append(f"{t} {title}")

                schedule_text = "   |   ".join(next_slots)

                with open(schedule_next_file + ".tmp", "w", encoding="utf-8") as f:
                    f.write(schedule_text)

                os.replace(schedule_next_file + ".tmp", schedule_next_file)

            except Exception as e:
                print(f"⚠️ Errore schedule box: {e}")
            # --- Fine prossimi eventi timeline overlay ---

        except Exception as e:
            print(f"⚠️ Errore Ticker Agent: {e}")

        time.sleep(2)


def check_singleton(name):
    import fcntl

    os.makedirs(RUNTIME_DIR, exist_ok=True)

    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")

    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)

        global _singleton_lock
        _singleton_lock = f

        f.write(str(os.getpid()))
        f.flush()

        return True
    except (IOError, OSError):
        print(f"❌ ERRORE: Un'altra istanza di {name} è già in esecuzione!")
        return False


if __name__ == "__main__":
    import sys

    if not check_singleton("ticker_agent"):
        print("❌ Uscita immediata per prevenire conflitti.")
        sys.exit(1)

    update_ticker()