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
        raw_news_file = os.path.join(TMP_DIR, "raw_news.json")
        default_news = {
            "title": "Nessuna notizia rilevante",
            "description": "Al momento non ci sono notizie rilevanti in evidenza. Restate sintonizzati su NewsicaTV per i prossimi aggiornamenti.",
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
            
            # Per rendere il canale dinamico, scegliamo una notizia a caso invece di quella più grave.
            # Questo garantisce che vengano toccati temi come sport, meteo, gossip, tech o benessere.
            selected_item = random.choice(news_list)
            
            # Assegniamo un "theme" fittizio basato sulle parole chiave per guidare i colori
            title_lower = selected_item.get('title', '').lower()
            if any(k in title_lower for k in ['sport', 'calcio', 'tennis', 'motori', 'atletica']):
                selected_item['theme_color'] = 'sport'
            elif any(k in title_lower for k in ['meteo', 'pioggia', 'sole', 'caldo', 'freddo']):
                selected_item['theme_color'] = 'meteo'
            elif any(k in title_lower for k in ['benessere', 'salute', 'dieta', 'dormire', 'medico']):
                selected_item['theme_color'] = 'wellness'
            elif any(k in title_lower for k in ['mort', 'guerra', 'attentato', 'grave']):
                selected_item['theme_color'] = 'breaking'
            else:
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
        tts_text = emoji.replace_emoji(tts_text, replace='')
        
        clean_text = prepare_text_for_tts(tts_text)
        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        # Voice if_sara represents Nora (News)
        samples, sample_rate = kokoro.create(clean_text, voice="if_sara", speed=1.1, lang="it")
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

    def _generate_background(self, theme: str = 'news', title: str = ''):
        print(f"🎨 Generazione background verticale dinamico (tema: {theme})...")
        width, height = 1080, 1920
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)
        
        import random
        # Palette dinamica base su temi
        if theme == 'sport':
            base_r, base_g, base_b = 200, 80, 20
        elif theme == 'meteo':
            base_r, base_g, base_b = 20, 100, 220
        elif theme == 'wellness':
            base_r, base_g, base_b = 40, 180, 90
        elif theme == 'breaking':
            base_r, base_g, base_b = 220, 20, 30
        else:
            palettes = [(140, 40, 220), (255, 60, 120), (10, 180, 200), (250, 180, 20)]
            base_r, base_g, base_b = random.choice(palettes)

        for y in range(height):
            r = int(base_r * (1 - (y / height) * 0.8))
            g = int(base_g * (1 - (y / height) * 0.8))
            b = int(base_b * (1 - (y / height) * 0.8))
            draw.line([(0, y), (width, y)], fill=(r, g, b))
            
        # DuckDuckGo Image Search e Overlay Immagine
        bg_image_added = False
        if title:
            try:
                print(f"🔎 Ricerca immagine contestuale per: {title}")
                with DDGS() as ddgs:
                    results = list(ddgs.images(title, max_results=1))
                    if results:
                        img_url = results[0].get("image")
                        print(f"🖼️ Immagine trovata: {img_url}")
                        resp = requests.get(img_url, timeout=10)
                        if resp.status_code == 200:
                            context_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                            # Resize to cover width and keep aspect ratio
                            w_percent = (width / float(context_img.size[0]))
                            h_size = int((float(context_img.size[1]) * float(w_percent)))
                            context_img = context_img.resize((width, h_size), Image.Resampling.LANCZOS)
                            
                            # Crea una sfocatura per non disturbare il testo
                            context_img = context_img.filter(ImageFilter.GaussianBlur(15))
                            
                            # Applica l'immagine al centro e abbassa l'opacità per fonderla col gradiente
                            context_img.putalpha(120)
                            y_pos = (height - h_size) // 2
                            image.paste(context_img, (0, y_pos), context_img)
                            bg_image_added = True
                            print("✅ Immagine di sfondo applicata con successo.")
            except Exception as e:
                logger.warning(f"Impossibile scaricare o applicare l'immagine da DDGS: {e}")

        # Se fallisce DDGS, pattern astratti fallback
        if not bg_image_added:
            for _ in range(5):
                cx = random.randint(0, width)
                cy = random.randint(0, height)
                radius = random.randint(300, 700)
                alpha = random.randint(10, 40)
                bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
                draw.ellipse(bbox, outline=(255, 255, 255, alpha), width=3)
            
        # Aggiungi il logo in cima (versione no background)
        logo_path = os.path.join(ASSETS_DIR, "logo_no_bg.png")
        if os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                max_logo_w = 400
                w_percent = (max_logo_w / float(logo.size[0]))
                h_size = int((float(logo.size[1]) * float(w_percent)))
                logo = logo.resize((max_logo_w, h_size), Image.Resampling.LANCZOS)
                
                x = (width - max_logo_w) // 2
                y = 150
                image.paste(logo, (x, y), logo)
            except Exception as e:
                logger.error(f"Impossibile caricare logo: {e}")
                
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
            # Prova font Mac classici
            if os.path.exists("/System/Library/Fonts/Helvetica.ttc"):
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 65)
            elif os.path.exists("/Library/Fonts/Arial.ttf"):
                font = ImageFont.truetype("/Library/Fonts/Arial.ttf", 65)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        frames_txt_path = os.path.join(TMP_DIR, "frames.txt")
        with open(frames_txt_path, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subs):
                frame_path = os.path.join(TMP_DIR, f"frame_{i}.png")
                frame = bg.copy()
                
                text = sub['text']
                # Usa Pilmoji per calcolare la larghezza (pilmoji si comporta diversamente da draw.textbbox, facciamo un fallback rapido per il centering)
                draw = ImageDraw.Draw(frame)
                try:
                    bbox = draw.textbbox((0, 0), text, font=font)
                    tw = bbox[2] - bbox[0]
                    # stima approssimativa extra per emoji, visto che draw.textbbox non sa bene come misurare le CBDT emoji
                    tw += text.count(emoji.emojize(':smile:')[0]) * 30 # placeholder logica molto empirica, ma la riga seguente risolve quasi sempre:
                except:
                    tw = 800

                x = (width - tw) / 2
                y = height / 2 + 150 # Pozizione in basso
                
                # Effetto Ombra / Bordo nero massiccio usando pilmoji
                with Pilmoji(frame) as pilmoji:
                    stroke_width = 4
                    for dx in range(-stroke_width, stroke_width+1, 2):
                        for dy in range(-stroke_width, stroke_width+1, 2):
                            pilmoji.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
                    
                    # Testo principale Giallo
                    pilmoji.text((x, y), text, font=font, fill=(255, 230, 0, 255))
                
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
            self._generate_background(theme, news.get('title', ''))
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
