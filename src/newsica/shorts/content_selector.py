from newsica.agents.content_strategist import ContentStrategistAgent

RETRIEVAL_PLACEHOLDER_SNIPPETS = {
    "nessuna notizia disponibile al momento",
    "stiamo aggiornando i nostri sistemi",
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return " ".join(str(text).split())


class ShortContentSelector:
    def _classify_theme_from_source(self, source: str) -> str:
        source = (source or "").lower()
        if "ultimora" in source or "breaking" in source:
            return "breaking"
        if "funfact" in source or "curios" in source:
            return "funfact"
        if "sport" in source:
            return "sport"
        if "salute" in source or "benessere" in source or "lifestyle" in source:
            return "wellness"
        if "tecnologia" in source or "innovazione" in source:
            return "tech"
        if "meteo" in source:
            return "meteo"
        return "news"

    def _load_all_news(self) -> list[dict]:
        strategist = ContentStrategistAgent()
        return strategist._collect_news(force_fetch=True)

    def _select_random_item(self, items: list[dict], default_item: dict) -> dict:
        if not items:
            return default_item
        import random

        return random.choice(items)

    def _build_mode_news_item(self, mode: str) -> dict:
        all_news = self._load_all_news()
        default_item = {
            "title": "Nessuna notizia disponibile al momento",
            "summary": "Stiamo aggiornando i nostri sistemi.",
            "description": "Stiamo aggiornando i nostri sistemi.",
            "source": mode,
            "theme_color": "news" if mode == "news" else mode,
        }

        mode_sources = {
            "breaking": {"ansa_ultimora"},
            "sport": {"ansa_sport", "agi_sport"},
            "meteo": {"meteo"},
            "tech": {"ansa_tecnologia", "agi_innovazione"},
            "wellness": {"ansa_salute_benessere", "ansa_lifestyle"},
        }

        if mode == "news":
            candidates = []
            for item in all_news:
                theme = self._classify_theme_from_source(item.get("source", ""))
                if theme == "news":
                    candidates.append(item)
            selected_item = self._select_random_item(candidates, default_item)
            selected_item["theme_color"] = "news"
            return selected_item

        candidates = [item for item in all_news if item.get("source") in mode_sources.get(mode, set())]
        selected_item = self._select_random_item(candidates, default_item)
        selected_item["theme_color"] = mode
        return selected_item

    def _build_funfact_news_item(self) -> dict:
        strategist = ContentStrategistAgent()
        all_news = self._load_all_news()
        candidate_sources = {
            "ansa_lifestyle",
            "ansa_cultura",
            "agi_cultura",
            "ansa_tecnologia",
            "agi_innovazione",
            "ansa_salute_benessere",
        }
        rss_candidates = [item for item in all_news if item.get("source") in candidate_sources]
        trend_brief = strategist.build_trend_brief(
            rss_items=rss_candidates[:6], format_type="shorts_funfact", deep_dive_results_limit=4
        )
        topic = trend_brief["topic"]
        deep_dive_results = trend_brief["deep_dive_results"]

        summary_lines = []
        for result in deep_dive_results[:4]:
            title = _normalize_text(result.get("title", ""))
            snippet = _normalize_text(result.get("snippet", ""))
            if title and snippet:
                summary_lines.append(f"{title}: {snippet}")
            elif title:
                summary_lines.append(title)
            elif snippet:
                summary_lines.append(snippet)

        summary = "\n".join(summary_lines).strip()
        if not summary:
            summary = "Curiosità del momento raccolte dal web e dagli ultimi trend rilevati online."

        return {
            "title": topic.get("title", "Curiosità del momento"),
            "summary": summary,
            "description": summary,
            "source": "funfact_web",
            "theme_color": "funfact",
        }

    def get_news_item_for_mode(self, mode: str) -> dict:
        if mode == "funfact":
            return self._build_funfact_news_item()
        if mode in {"breaking", "sport", "meteo", "tech", "wellness", "news"}:
            return self._build_mode_news_item(mode)
        return self._build_mode_news_item("news")

    def _is_retrieval_placeholder(self, value: str) -> bool:
        normalized = _normalize_text(value).lower()
        if not normalized:
            return True
        for snippet in RETRIEVAL_PLACEHOLDER_SNIPPETS:
            if snippet in normalized:
                return True
        return False

    def validate_news_item_for_short(self, news_item: dict, mode: str) -> tuple[bool, str]:
        title = _normalize_text(news_item.get("title", ""))
        summary = _normalize_text(news_item.get("summary") or news_item.get("description") or "")
        source = _normalize_text(news_item.get("source", "")).lower()

        if self._is_retrieval_placeholder(title) or self._is_retrieval_placeholder(summary):
            return False, "Retrieve news degradato: placeholder rilevato nel contenuto."
        if mode in {"news", "breaking"} and source in {"news", "breaking"}:
            return False, "Retrieve news degradato: sorgente fallback non editoriale."
        return True, ""
