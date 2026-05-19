from newsica.sources.registry import WELLNESS_PREFERRED_SOURCES
from newsica.sources.rotation import item_key, load_json, write_json

WELLNESS_KEYWORDS = (
    "fitness", "allenamento", "sport", "cammin", "corsa", "palestra",
    "benessere", "salute", "sonno", "stress", "aliment", "nutriz",
    "cura", "pelle", "corpo", "mente", "emozion", "prevenzione",
    "abitudine", "fiori", "stelle", "viaggio", "estate",
)
WELLNESS_PENALTY_KEYWORDS = (
    "sciopero", "ebola", "vittime", "morto", "ricovero", "condanna",
    "emergenza", "tagliati", "diabete", "farmaci", "allergia", "epidemia",
)


def wellness_score(item):
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    score = sum(1 for keyword in WELLNESS_KEYWORDS if keyword in text)
    score -= 3 * sum(1 for keyword in WELLNESS_PENALTY_KEYWORDS if keyword in text)
    if item.get("source") == "ansa_lifestyle":
        score += 4
    if item.get("source") == "ansa_salute_benessere":
        score += 3
    return score


def select_fresh_wellness(items, recent_file, limit=3):
    recent = load_json(recent_file, [])
    ranked = sorted(items, key=wellness_score, reverse=True)
    light_items = [
        item for item in ranked
        if item.get("source") in {"ansa_salute_benessere", "ansa_lifestyle"} or wellness_score(item) >= 2
    ]
    fresh = [item for item in light_items if item_key(item) not in recent]
    candidates = fresh if fresh else light_items if light_items else ranked
    selected = []

    for preferred_source in WELLNESS_PREFERRED_SOURCES:
        preferred_candidates = [item for item in candidates if item.get("source") == preferred_source]
        for item in preferred_candidates:
            if item not in selected:
                selected.append(item)
                break

    for item in candidates:
        if item not in selected:
            selected.append(item)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for item in ranked:
            if item not in selected:
                selected.append(item)
            if len(selected) >= limit:
                break

    write_json(recent_file, (recent + [item_key(item) for item in selected])[-60:])
    return selected

