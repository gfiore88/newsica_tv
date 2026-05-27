import os
import json
import logging
import requests
import datetime
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import soundfile as sf
from kokoro_onnx import Kokoro
from newsica.audio.tts_text import prepare_text_for_tts
from newsica.editorial.gravity_assessor import calculate_heuristic_score
import emoji
from duckduckgo_search import DDGS
import io

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:12b")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "shorts")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

class ShortsAgent:
    def __init__(self):
        self.tmp_audio = os.path.join(TMP_DIR, "short_audio.wav")
        self.tmp_srt = os.path.join(TMP_DIR, "short.srt")
        self.tmp_bg = os.path.join(TMP_DIR, "shorts_bg.png")

    def _get_top_news(self) -> dict:
        raw_news_file = os.path.join(TMP_DIR, 'raw_news.json')
        default_news = {
            "title": "Nessuna notizia disponibile al momento",
            "summary": "Stiamo aggiornando i nostri sistemi.",
            "category": "news"
        }
        
        if not os.path.exists(raw_news_file):
            return default_news

        try:
            with open(raw_news_file, 'r', encoding='utf-8') as f:
                news_list = json.load(f)
            
            if not news_list:
                return default_news
                
            import random
            
            # Scegliamo una notizia a caso
            selected_item = random.choice(news_list)
            
            # Targeting serio tramite SOURCE invece di usare string matching sul titolo
            source = selected_item.get('source', '').lower()
            
            if 'sport' in source:
                selected_item['theme_color'] = 'sport'
            elif 'salute' in source or 'benessere' in source or 'lifestyle' in source:
                selected_item['theme_color'] = 'wellness'
            elif 'tecnologia' in source or 'innovazione' in source:
                selected_item['theme_color'] = 'tech'
            elif 'meteo' in source:
                selected_item['theme_color'] = 'meteo'
            else:
                # Per cronaca, mondo, politica e ultimora
                selected_item['theme_color'] = 'news'

            return selected_item
            
        except Exception as e:
            logger.error(f"Errore nella lettura news: {e}")
            return default_news

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
            "options": {"temperature": 0.8, "num_predict": 100}
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

    def _generate_audio(self, text: str) -> float:
        print("🎙️ Generazione audio TTS per lo Short...")
        # 1. Rimuoviamo hashtag e prepariamo il testo
        tts_text = text.replace("#", "")
        # 2. Rimuoviamo tutte le emoji dal testo destinato al TTS
        import emoji
        tts_text = emoji.replace_emoji(tts_text, replace='')
        
        clean_text = prepare_text_for_tts(tts_text)
        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        
        # Scelta random tra voce maschile e femminile
        import random
        voices = ["if_sara", "im_nicola"]
        selected_voice = random.choice(voices)
        print(f"🗣️ Voce TTS selezionata: {selected_voice}")
        
        samples, sample_rate = kokoro.create(clean_text, voice=selected_voice, speed=1.1, lang="it")
        sf.write(self.tmp_audio, samples, sample_rate)
        
        duration = len(samples) / sample_rate
        return duration

    def _generate_srt(self, text: str, duration: float):
        print("📝 Generazione file sottotitoli SRT (Character-based sync)...")
        words = text.split()
        # Raggruppa in chunk da 3 parole
        chunks = [" ".join(words[i:i+3]) for i in range(0, len(words), 3)]
        
        # Calcolo dei tempi basato sul numero di caratteri (ignorando gli spazi) per un sync perfetto
        total_chars = sum(len(c.replace(" ", "")) for c in chunks)
        time_per_char = duration / total_chars if total_chars > 0 else 1.0
        
        def format_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        with open(self.tmp_srt, 'w', encoding='utf-8') as f:
            current_time = 0.0
            for i, chunk in enumerate(chunks):
                start_time = current_time
                chunk_chars = len(chunk.replace(" ", ""))
                chunk_duration = chunk_chars * time_per_char
                end_time = start_time + chunk_duration
                
                f.write(f"{i+1}\n")
                f.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
                f.write(f"{chunk}\n\n")
                
                current_time = end_time

    def _download_image(self, img_url: str):
        if not img_url:
            return None
        try:
            headers = {"User-Agent": "NewsicaTV/1.0"}
            response = requests.get(img_url, headers=headers, timeout=15)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if "image" not in content_type:
                logger.warning(f"URL non immagine: {img_url} - Content-Type: {content_type}")
                return None
            img = Image.open(io.BytesIO(response.content)).convert("RGBA")
            min_w, min_h = 400, 300
            if img.width < min_w or img.height < min_h:
                logger.warning(f"Immagine troppo piccola scartata: {img.width}x{img.height} - {img_url}")
                return None
            return img
        except Exception as e:
            logger.warning(f"Download immagine fallito: {img_url} - {e}")
            return None

    def _apply_context_image_to_background(self, image: Image.Image, context_img: Image.Image):
        # La mettiamo in un riquadro centrale per non coprire i loghi del base screen
        width, height = image.size
        box_w, box_h = 980, 700
        
        img_w, img_h = context_img.size
        scale = max(box_w / img_w, box_h / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        
        context_img = context_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - box_w) // 2
        top = (new_h - box_h) // 2
        context_img = context_img.crop((left, top, left + box_w, top + box_h))
        
        # Sfumatura ai bordi (effetto vignettatura) o opacità ridotta per amalgamarsi
        context_img.putalpha(190)
        
        # Posizionala al centro-alto (lasciando spazio sotto per i testi)
        y_pos = (height - box_h) // 2 - 150
        x_pos = (width - box_w) // 2
        
        image.paste(context_img, (x_pos, y_pos), context_img)
        return image

    def _search_pexels_image_via_llm(self, title: str):
        pexels_key = os.getenv("PEXELS_API_KEY")
        if not pexels_key:
            return None
            
        try:
            import urllib.parse
            prompt = f'Given the news title: "{title}". Extract a SINGLE generic English keyword that visually represents the subject (e.g. if the news is about an Italian hospital, write "hospital". If it is about police, write "police car"). Reply ONLY with the English keyword, no punctuation.'
            payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
            resp = requests.post(OLLAMA_URL, json=payload, timeout=10)
            if resp.status_code == 200:
                keyword = resp.json().get("response", "").strip()
                if keyword:
                    print(f"🔎 Keyword Pexels estratta: {keyword}")
                    q = urllib.parse.quote(keyword)
                    url = f"https://api.pexels.com/v1/search?query={q}&per_page=1&orientation=landscape"
                    pex_resp = requests.get(url, headers={"Authorization": pexels_key}, timeout=10)
                    if pex_resp.status_code == 200:
                        data = pex_resp.json()
                        if data.get("photos"):
                            return data["photos"][0]["src"].get("landscape") or data["photos"][0]["src"].get("large")
        except Exception as e:
            logger.warning(f"Errore Pexels via LLM: {e}")
        return None

    def _search_wikipedia_image_via_llm(self, title: str):
        try:
            import urllib.parse
            prompt = f'Data la notizia: "{title}". Estrai una SINGOLA entità Wikipedia (una città, un personaggio pubblico, o un oggetto generico come "Ospedale" o "Polizia"). Rispondi SOLO con il nome dell entità, niente punteggiatura.'
            payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
            resp = requests.post(OLLAMA_URL, json=payload, timeout=10)
            if resp.status_code == 200:
                entity = resp.json().get("response", "").strip()
                if entity:
                    print(f"🔎 Entità Wikipedia estratta: {entity}")
                    q = urllib.parse.quote(entity)
                    url = f"https://it.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&generator=search&gsrsearch={q}&pithumbsize=1200"
                    wiki_resp = requests.get(url, headers={"User-Agent": "NewsicaTV/1.0"}, timeout=10)
                    if wiki_resp.status_code == 200:
                        pages = wiki_resp.json().get("query", {}).get("pages", {})
                        for _, page in pages.items():
                            if "thumbnail" in page:
                                return page["thumbnail"]["source"]
        except Exception as e:
            logger.warning(f"Errore Wikipedia via LLM: {e}")
        return None

    def _generate_background(self, theme: str = 'news', title: str = '', image_url: str = ''):
        print(f"🎨 Generazione background verticale dinamico (tema: {theme})...")
        width, height = 1080, 1920
        
        base_bg_path = os.path.join(ASSETS_DIR, "shorts_backgrounds", "base_screens", f"{theme}.png")
        if not os.path.exists(base_bg_path):
            base_bg_path = os.path.join(ASSETS_DIR, "shorts_backgrounds", "base_screens", "news.png")
            
        if os.path.exists(base_bg_path):
            image = Image.open(base_bg_path).convert("RGB")
            if image.size != (width, height):
                image = image.resize((width, height), Image.Resampling.LANCZOS)
        else:
            image = Image.new("RGB", (width, height), color=(20, 20, 20))
            
        context_img = None
        
        if image_url:
            print(f"🖼️ Uso immagine originale dalla news: {image_url}")
            context_img = self._download_image(image_url)
            
        if not context_img and title:
            print("🔎 Cerco immagine ad alto impatto...")
            remote_url = self._search_pexels_image_via_llm(title)
            
            # Fallback intelligente su Wikipedia
            if not remote_url:
                remote_url = self._search_wikipedia_image_via_llm(title)
                
            if remote_url:
                print(f"🖼️ Immagine remota trovata: {remote_url}")
                context_img = self._download_image(remote_url)
                
        # 5. Applica immagine
        if context_img is not None:
            image = self._apply_context_image_to_background(image, context_img)
            print("✅ Immagine in sovraimpressione applicata con successo.")
        else:
            print("ℹ️ Nessuna immagine fornita dall'RSS. Uso solo lo sfondo tematico pulito.")

        # Aggiungi il logo in cima (versione no background) - ATTUALMENTE DISABILITATO 
        # (Il logo è già presente nativamente nei base_screens)
        # logo_path = os.path.join(ASSETS_DIR, "logo_no_bg.png")
        # if os.path.exists(logo_path):
        #     try:
        #         logo = Image.open(logo_path).convert("RGBA")
        #         max_logo_w = 400
        #         w_percent = (max_logo_w / float(logo.size[0]))
        #         h_size = int((float(logo.size[1]) * float(w_percent)))
        #         logo = logo.resize((max_logo_w, h_size), Image.Resampling.LANCZOS)
        #         
        #         x = (width - max_logo_w) // 2
        #         y = 150
        #         image.paste(logo, (x, y), logo)
        #     except Exception as e:
        #         logger.error(f"Impossibile caricare logo: {e}")
                
        image.save(self.tmp_bg)

    def _render_video(self):
        from pilmoji import Pilmoji
        import re
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(OUTPUT_DIR, f"short_{timestamp}.mp4")
        print(f"🎬 Rendering video finale con FFmpeg verso: {output_file}...")
        
        # 1. Parsing del file SRT
        subs = []
        if os.path.exists(self.tmp_srt):
            with open(self.tmp_srt, 'r', encoding='utf-8') as f:
                content = f.read()
            blocks = content.strip().split('\n\n')
            for block in blocks:
                lines = block.split('\n')
                if len(lines) >= 3:
                    time_line = lines[1]
                    text = " ".join(lines[2:])
                    m = re.match(r'(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)', time_line)
                    if m:
                        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
                        start = h1*3600 + m1*60 + s1 + ms1/1000.0
                        end = h2*3600 + m2*60 + s2 + ms2/1000.0
                        subs.append({"duration": end - start, "text": text})

        # 2. Generazione Frame con Sottotitoli sovraimpressi via PIL
        bg = Image.open(self.tmp_bg).convert("RGBA")
        width, height = bg.size
        
        try:
            # Prova font Mac in grassetto per maggiore leggibilità
            if os.path.exists("/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 75)
            elif os.path.exists("/System/Library/Fonts/Helvetica.ttc"):
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 75)
            elif os.path.exists("/Library/Fonts/Arial.ttf"):
                font = ImageFont.truetype("/Library/Fonts/Arial.ttf", 75)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        frames_txt_path = os.path.join(TMP_DIR, "frames.txt")
        with open(frames_txt_path, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subs):
                frame_path = os.path.join(TMP_DIR, f"frame_{i}.png")
                frame = bg.copy()
                
                import textwrap
                text = sub['text'].upper()
                lines = textwrap.wrap(text, width=22)
                
                draw = ImageDraw.Draw(frame)
                
                try:
                    # Calcolo altezza riga in base al font
                    bbox_h = draw.textbbox((0, 0), "A", font=font)
                    line_height = bbox_h[3] - bbox_h[1] + 20
                except:
                    line_height = 95

                total_height = len(lines) * line_height
                start_y = (height / 2 + 150) - (total_height / 2)
                
                with Pilmoji(frame) as pilmoji:
                    for idx, line in enumerate(lines):
                        try:
                            bbox = draw.textbbox((0, 0), line, font=font)
                            tw = bbox[2] - bbox[0]
                            tw += line.count(emoji.emojize(':smile:')[0]) * 30
                        except:
                            tw = 800
                            
                        x = (width - tw) / 2
                        y = start_y + (idx * line_height)
                        
                        stroke_width = 4
                        for dx in range(-stroke_width, stroke_width+1, 2):
                            for dy in range(-stroke_width, stroke_width+1, 2):
                                pilmoji.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
                        
                        pilmoji.text((x, y), line, font=font, fill=(255, 230, 0, 255))
                
                frame.save(frame_path)
                
                # Scrivi record concat (escaped quote per sicurezza anche se frame_i non ha apici)
                f.write(f"file 'frame_{i}.png'\n")
                f.write(f"duration {sub['duration']:.3f}\n")
            
            # Necessario per ffmpeg concat demuxer: ripetere l'ultimo file
            if subs:
                f.write(f"file 'frame_{len(subs)-1}.png'\n")

        # 3. Composizione Video via Concat Demuxer
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", frames_txt_path,
            "-i", self.tmp_audio,
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_file
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"✅ Short generato con successo: {output_file}")
            return output_file
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode()
            print(f"❌ Errore FFmpeg: {error_msg}")
            raise RuntimeError(f"FFmpeg Error: {error_msg}")

    def run(self) -> dict:
        try:
            news = self._get_top_news()
            theme = news.get('theme_color', 'news')
            script = self._generate_script(news)
            duration = self._generate_audio(script)
            self._generate_srt(script, duration)
            img_url = news.get('image_url') or news.get('urlToImage', '')
            self._generate_background(theme, news.get('title', ''), img_url)
            out_file = self._render_video()
            
            return {
                "status": "success" if out_file else "failed",
                "output": out_file,
                "script": script,
                "news_title": news.get('title', '')
            }
        except Exception as e:
            logger.error(f"Errore critico in ShortsAgent: {e}")
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    agent = ShortsAgent()
    agent.run()
