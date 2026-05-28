import os
import json
import logging
import requests
import datetime
import subprocess
from newsica.shorts.caption_builder import generate_social_copy
from newsica.shorts.content_selector import ShortContentSelector
import newsica.shorts.render_pipeline as render_pipeline_module
from newsica.shorts.render_pipeline import ShortRenderPipeline
from newsica.storage.repositories.shorts_library_repository import upsert_short
from newsica.shorts.constants import SHORT_MODES
import re
from kokoro_onnx import Kokoro

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:12b")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "shorts")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

SUPPORTED_SHORT_MODES = {
    *SHORT_MODES,
}

class ShortsAgent:
    def __init__(self):
        # Keep module-level test patch points stable after pipeline extraction.
        render_pipeline_module.Kokoro = Kokoro
        self.content_selector = ShortContentSelector()
        self.render_pipeline = ShortRenderPipeline(
            tmp_dir=TMP_DIR,
            assets_dir=ASSETS_DIR,
            output_dir=OUTPUT_DIR,
            ollama_url=OLLAMA_URL,
            model_name=MODEL_NAME,
        )
        self.tmp_audio = self.render_pipeline.tmp_audio
        self.tmp_srt = self.render_pipeline.tmp_srt
        self.tmp_bg = self.render_pipeline.tmp_bg

    def _classify_theme_from_source(self, source: str) -> str:
        return self.content_selector._classify_theme_from_source(source)

    def _build_mode_news_item(self, mode: str) -> dict:
        return self.content_selector._build_mode_news_item(mode)

    def _build_funfact_news_item(self) -> dict:
        return self.content_selector._build_funfact_news_item()

    def _get_news_item_for_mode(self, mode: str) -> dict:
        if mode == "funfact":
            return self._build_funfact_news_item()
        if mode in {"breaking", "sport", "meteo", "tech", "wellness", "motori", "news"}:
            return self._build_mode_news_item(mode)
        return self._build_mode_news_item("news")

    def _is_retrieval_placeholder(self, value: str) -> bool:
        return self.content_selector._is_retrieval_placeholder(value)

    def _validate_news_item_for_short(self, news_item: dict, mode: str) -> tuple[bool, str]:
        return self.content_selector.validate_news_item_for_short(news_item, mode)

    def _generate_script(self, news_item: dict) -> str:
        prompt_path = os.path.join(BASE_DIR, "src", "newsica", "editorial", "prompts", "shorts.md")
        system_prompt = ""
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    system_prompt = f.read()
            except Exception as e:
                logger.error(f"⚠️ Impossibile leggere il prompt degli shorts: {e}")
                
        if not system_prompt:
            system_prompt = "Sei un copywriter per YouTube Shorts, specializzato in contenuti giovanili e virali. Scrivi un copione ultra-breve (MASSIMO 40 parole) basato sulla notizia fornita in coda."
            
        prompt = f"""{system_prompt}

Notizia: {news_item.get('title')}
{news_item.get('description')}
"""
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.8, "num_predict": 300}
        }
        
        try:
            print("🧠 Generazione script Short tramite Ollama...")
            response = requests.post(OLLAMA_URL, json=payload, timeout=30)
            response.raise_for_status()
            script = response.json().get("response", "").strip()
            return script if script else "Oggi su Newsica TV un aggiornamento imperdibile! Restate connessi."
        except Exception as e:
            logger.error(f"Errore LLM: {e}")
            return "Ultim'ora pazzesca! " + news_item.get('title', '') + ". Che ne pensate? Scrivetelo nei commenti!"

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", str(text)).strip()
        return text

    def _generate_audio(self, text: str, theme_or_mode: str = None) -> tuple[float, str]:
        """Delega a render_pipeline e propaga la tupla (durata, testo_pulito)."""
        return self.render_pipeline.generate_audio(text, theme_or_mode)

    def _generate_srt(self, text: str, duration: float):
        self.render_pipeline.generate_srt(text, duration)

    def _download_image(self, img_url: str):
        return self.render_pipeline._download_image(img_url)

    def _apply_context_image_to_background(self, image, context_img):
        return self.render_pipeline._apply_context_image_to_background(image, context_img)

    def _search_pexels_image_via_llm(self, title: str):
        return self.render_pipeline._search_pexels_image_via_llm(title)

    def _search_wikipedia_image_via_llm(self, title: str):
        return self.render_pipeline._search_wikipedia_image_via_llm(title)

    def _generate_background(self, theme: str = 'news', title: str = '', image_url: str = ''):
        self.render_pipeline.generate_background(theme=theme, title=title, image_url=image_url)

    def _render_video(self):
        return self.render_pipeline.render_video()

    def _write_metadata(self, output_file: str, news_item: dict, script: str, caption: str, hashtags: list[str]):
        metadata_path = os.path.splitext(output_file)[0] + ".json"
        filename = os.path.basename(output_file)
        theme = news_item.get("theme_color", "news")
        mode = news_item.get("short_mode", theme)
        payload = {
            "news_title": news_item.get("title", ""),
            "script": script,
            "caption": caption,
            "hashtags": hashtags[:5],
            "theme": theme,
            "mode": mode,
            "created_at": datetime.datetime.now().isoformat(),
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        upsert_short(
            filename=filename,
            video_path=output_file,
            mode=mode,
            theme=theme,
            news_title=news_item.get("title", ""),
            script=script,
            caption=caption,
            hashtags=hashtags[:5],
        )

    def run(self, mode="news", news_item: dict = None) -> dict:
        try:
            if news_item:
                news = news_item
            else:
                news = self._get_news_item_for_mode(mode)
            news["short_mode"] = mode
            is_valid, validation_error = self._validate_news_item_for_short(news, mode)
            if not is_valid:
                logger.error(f"Short annullato [{mode}]: {validation_error}")
                return {
                    "status": "retrieval_failed",
                    "message": validation_error,
                    "mode": mode,
                }
            theme = news.get('theme_color', 'news')
            script = self._generate_script(news)
            caption, hashtags = generate_social_copy(news, script)
            duration, clean_script = self._generate_audio(script, mode)
            self._generate_srt(clean_script, duration)
            img_url = news.get('image_url') or news.get('urlToImage', '')
            self._generate_background(theme, news.get('title', ''), img_url)
            out_file = self._render_video()
            self._write_metadata(out_file, news, script, caption, hashtags)
            
            # Pubblicazione automatica sui social se abilitata nell'ambiente
            from newsica.shorts.social_service import (
                build_full_caption,
                publish_short,
                track_social_posts,
            )
            from newsica.utils.social_publisher import SocialPublisher
            if SocialPublisher.is_auto_post_enabled():
                print("📢 Auto-posting abilitato! Avvio della pubblicazione automatica...")
                title = news.get("title", "Short NewsicaTV")
                full_caption = build_full_caption(caption, hashtags)
                post_result = publish_short(out_file, title, full_caption, "all")
                track_social_posts(os.path.basename(out_file), "all", post_result)
            
            return {
                "status": "success" if out_file else "failed",
                "output": out_file,
                "script": script,
                "news_title": news.get('title', ''),
                "caption": caption,
                "hashtags": hashtags,
                "mode": mode,
            }
        except Exception as e:
            logger.error(f"Errore critico in ShortsAgent: {e}")
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    agent = ShortsAgent()
    agent.run()
