import re
import unicodedata


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _build_hashtag(text: str) -> str:
    cleaned = unicodedata.normalize("NFKD", text or "")
    cleaned = cleaned.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", cleaned)
    parts = [part for part in cleaned.split() if part]
    if not parts:
        return ""
    return "#" + "".join(part.capitalize() for part in parts[:3])


def _extract_keyword_hashtags(text: str) -> list[str]:
    stopwords = {
        "alla", "allo", "anche", "ancora", "avere", "come", "con", "dalla", "dalle",
        "degli", "della", "delle", "dello", "dentro", "dopo", "fare", "gli", "hanno",
        "italia", "loro", "nelle", "nello", "newsica", "newsicatv", "oggi", "perche",
        "pero", "prima", "quale", "quando", "quella", "quello", "questa", "questo",
        "sara", "sono", "sotto", "sulla", "sulle", "tutto", "ultime", "ultima", "ultimora",
        "verso", "dove", "degli", "dati", "dopo", "delle", "della", "dello", "dell",
        "nella", "nelle", "negli", "sugli", "sugli", "dall", "dallo", "dalla", "dalle",
    }
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    tokens = re.findall(r"[a-z0-9]{4,}", normalized)
    hashtags = []
    seen = set()
    for token in tokens:
        if token in stopwords:
            continue
        hashtag = _build_hashtag(token)
        if not hashtag:
            continue
        lowered = hashtag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        hashtags.append(hashtag)
    return hashtags


def generate_social_copy(news_item: dict, script: str) -> tuple[str, list[str]]:
    title = normalize_text(news_item.get("title", ""))
    script_text = normalize_text(script)
    theme = (news_item.get("theme_color") or "news").lower()

    theme_hashtags = {
        "news": ["#Ultimora", "#Notizie", "#Italia"],
        "breaking": ["#BreakingNews", "#UltimOra", "#NewsFlash"],
        "sport": ["#SportNews", "#Sport", "#Highlights"],
        "tech": ["#TechNews", "#Tecnologia", "#Innovazione"],
        "wellness": ["#Salute", "#Benessere", "#Lifestyle"],
        "funfact": ["#FunFact", "#Curiosita", "#Viralita"],
        "meteo": ["#Meteo", "#Previsioni", "#Italia"],
    }

    script_for_caption = re.sub(r"\s*#\w+", "", script_text).strip()
    caption_parts = []
    if title:
        caption_parts.append(title)
    if script_for_caption:
        caption_parts.append(script_for_caption)
    caption_parts.append("Seguici per altri aggiornamenti in tempo reale.")
    caption = "\n\n".join(part for part in caption_parts if part)

    hashtags = ["#NewsicaTV"]
    hashtags.extend(theme_hashtags.get(theme, theme_hashtags["news"]))
    hashtags.extend(_extract_keyword_hashtags(f"{title} {script_text}"))

    unique_hashtags = []
    seen = set()
    for hashtag in hashtags:
        lowered = hashtag.lower()
        if not hashtag or lowered in seen:
            continue
        seen.add(lowered)
        unique_hashtags.append(hashtag)
        if len(unique_hashtags) == 5:
            break

    fallback_hashtags = ["#BreakingNews", "#ViralNews", "#Aggiornamento"]
    for hashtag in fallback_hashtags:
        if len(unique_hashtags) == 5:
            break
        lowered = hashtag.lower()
        if lowered not in seen:
            seen.add(lowered)
            unique_hashtags.append(hashtag)

    return caption, unique_hashtags[:5]
