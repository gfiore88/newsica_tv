import hashlib
import json


def item_key(item):
    value = item.get("link") or item.get("title", "")
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def normalized_title_key(item):
    title = item.get("title", "").lower()
    letters = [char if char.isalnum() else " " for char in title]
    words = [word for word in "".join(letters).split() if len(word) > 3]
    return " ".join(words[:8])


def title_tokens(item):
    title = item.get("title", "").lower()
    letters = [char if char.isalnum() else " " for char in title]
    stopwords = {
        "della", "delle", "degli", "dalla", "dalle", "alla", "alle",
        "sono", "come", "anche", "dopo", "prima", "oggi", "live",
        "diretta", "agli", "allo", "nella", "nelle", "sulla", "sulle",
    }
    return {
        word for word in "".join(letters).split()
        if len(word) > 3 and word not in stopwords
    }


def is_similar_story(item, selected):
    current_tokens = title_tokens(item)
    if not current_tokens:
        return False

    for existing in selected:
        existing_tokens = title_tokens(existing)
        if not existing_tokens:
            continue
        common = current_tokens & existing_tokens
        union = current_tokens | existing_tokens
        if len(common) >= 2 and len(common) / len(union) >= 0.25:
            return True
    return False


def select_rotating_items(items, group, limit, recent_file, preferred_sources=None):
    recent = load_json(recent_file, {})
    recent_keys = set(recent.get(group, []))
    preferred_sources = preferred_sources or []
    selected = []
    selected_title_keys = set()
    selected_keys = set()

    def add_item(item):
        key = item_key(item)
        title_key = normalized_title_key(item)
        if key in selected_keys:
            return False
        if title_key and title_key in selected_title_keys:
            return False
        if is_similar_story(item, selected):
            return False
        selected.append(item)
        selected_keys.add(key)
        if title_key:
            selected_title_keys.add(title_key)
        return True

    def candidates_for(source=None, fresh_only=True):
        candidates = items
        if source:
            candidates = [item for item in candidates if item.get("source") == source]
        if fresh_only:
            candidates = [item for item in candidates if item_key(item) not in recent_keys]
        return candidates

    for source in preferred_sources:
        for item in candidates_for(source, fresh_only=True):
            if add_item(item):
                break

    source_order = preferred_sources + [
        source for source in sorted({item.get("source") for item in items})
        if source not in preferred_sources
    ]
    for fresh_only in (True, False):
        made_progress = True
        while len(selected) < limit and made_progress:
            made_progress = False
            for source in source_order:
                for item in candidates_for(source, fresh_only=fresh_only):
                    if add_item(item):
                        made_progress = True
                        break
                if len(selected) >= limit:
                    break
        if len(selected) >= limit:
            break

    recent[group] = recent.get(group, []) + [item_key(item) for item in selected]
    compact = {recent_group: keys[-160:] for recent_group, keys in recent.items()}
    write_json(recent_file, compact)
    return selected[:limit]

