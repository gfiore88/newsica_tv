import json
import time
from datetime import datetime
from newsica.config.paths import TMP_DIR
from newsica.sources.collector import collect_news_items
from newsica.domain.characters import get_character
from newsica.editorial.source_filters import filter_items_for_character, fallback_general_news
from newsica.editorial.fallback_scripts import build_fallback_script

class ContentStrategistAgent:
    def __init__(self, cache_seconds=900):
        self.cache_seconds = cache_seconds
        self.output_file = TMP_DIR / "raw_news.json"
        
    def _should_use_cache(self, force_fetch=False):
        if force_fetch or not self.output_file.exists():
            return False
        age = time.time() - self.output_file.stat().st_mtime
        if age < self.cache_seconds:
            print(f"[{datetime.now()}] Cache valida ({int(age)}s di età). Salto lo scraping di rete.")
            return True
        return False
        
    def _collect_news(self, force_fetch=False):
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        if self._should_use_cache(force_fetch):
            return json.loads(self.output_file.read_text(encoding="utf-8"))
            
        print(f"[{datetime.now()}] Avvio scraping delle news...")
        all_news = collect_news_items()
        self.output_file.write_text(json.dumps(all_news, ensure_ascii=False, indent=4), encoding="utf-8")
        print(f"[{datetime.now()}] Scraping completato. Salvate {len(all_news)} notizie in {self.output_file}")
        return all_news

    def _build_prompt_payload(self, news_items):
        news_text = "Ecco le notizie da rielaborare:\n\n"
        for item in news_items:
            news_text += f"- TITOLO: {item.get('title', '')}\n"
            news_text += f"  SINTESI: {item.get('summary', '')}\n\n"
        return news_text

    def prepare_content(self, character_id, title=None, force_fetch=False):
        """
        Prepara le istruzioni e il contesto per l'AI Integrator.
        Restituisce un dizionario con i dati strutturati.
        """
        character = get_character(character_id)
        all_news = self._collect_news(force_fetch)
        
        filtered_news = filter_items_for_character(all_news, character)
        if not filtered_news:
            print(f"⚠️ Nessuna notizia specifica per '{character.id}'. Uso quelle generali.")
            filtered_news = fallback_general_news(all_news)
            
        fallback_script = build_fallback_script(character.id, filtered_news)
        prompt = self._build_prompt_payload(filtered_news)
        system_prompt = character.read_prompt()
        
        intro = ""
        if title:
            intro = character.render_intro(title)
            
        return {
            "character_id": character.id,
            "display_name": character.display_name,
            "title": title,
            "intro": intro,
            "system_prompt": system_prompt,
            "prompt": prompt,
            "fallback_script": fallback_script,
            "voice": character.voice,
            "speed": character.speed,
        }
