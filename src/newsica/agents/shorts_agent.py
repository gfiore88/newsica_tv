import os
import json
import logging
import requests
import datetime
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont
import soundfile as sf
from kokoro_onnx import Kokoro
from newsica.audio.tts_text import prepare_text_for_tts
from newsica.editorial.gravity_assessor import calculate_heuristic_score

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
        clean_text = prepare_text_for_tts(text)
        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        # Voice if_sara represents Nora (News)
        samples, sample_rate = kokoro.create(clean_text, voice="if_sara", speed=1.1, lang="it")
        sf.write(self.tmp_audio, samples, sample_rate)
        
        duration = len(samples) / sample_rate
        return duration

    def _generate_srt(self, text: str, duration: float):
        print("📝 Generazione file sottotitoli SRT...")
        words = text.split()
        # Raggruppa in chunk da 3 parole
        chunks = [" ".join(words[i:i+3]) for i in range(0, len(words), 3)]
        
        chunk_duration = duration / len(chunks) if chunks else 1.0
        
        def format_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        with open(self.tmp_srt, 'w', encoding='utf-8') as f:
            for i, chunk in enumerate(chunks):
                start_time = i * chunk_duration
                end_time = (i + 1) * chunk_duration
                
                f.write(f"{i+1}\n")
                f.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
                f.write(f"{chunk}\n\n")

    def _generate_background(self, theme: str = 'news'):
        print(f"🎨 Generazione background verticale dinamico (tema: {theme})...")
        width, height = 1080, 1920
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)
        
        import random
        # Palette dinamica base su temi
        if theme == 'sport':
            base_r, base_g, base_b = 200, 80, 20  # Arancio/Rosso sportivo
        elif theme == 'meteo':
            base_r, base_g, base_b = 20, 100, 220 # Blu cielo/Meteo
        elif theme == 'wellness':
            base_r, base_g, base_b = 40, 180, 90  # Verde salute
        elif theme == 'breaking':
            base_r, base_g, base_b = 220, 20, 30  # Rosso allarme
        else:
            # Colori pop giovanili casuali per la cronaca (Viola, Rosa, Ciano)
            palettes = [
                (140, 40, 220), # Viola
                (255, 60, 120), # Rosa acceso
                (10, 180, 200), # Ciano neon
                (250, 180, 20), # Giallo/Oro
            ]
            base_r, base_g, base_b = random.choice(palettes)

        # Crea un gradiente dinamico
        for y in range(height):
            # Sfuma verso un colore scuro (nero/blu notte) in basso
            r = int(base_r * (1 - (y / height) * 0.8))
            g = int(base_g * (1 - (y / height) * 0.8))
            b = int(base_b * (1 - (y / height) * 0.8))
            draw.line([(0, y), (width, y)], fill=(r, g, b))
            
        # Aggiungi pattern astratti (cerchi morbidi sfocati)
        for _ in range(5):
            cx = random.randint(0, width)
            cy = random.randint(0, height)
            radius = random.randint(300, 700)
            alpha = random.randint(10, 40)
            
            # Un overlay molto naif (per non usare compositing complesso di Pillow)
            bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
            draw.ellipse(bbox, outline=(255, 255, 255, alpha), width=3)
            
        # Aggiungi il logo in cima
        logo_path = os.path.join(ASSETS_DIR, "logo.png")
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
                draw = ImageDraw.Draw(frame)
                
                text = sub['text']
                # Centratura testo
                try:
                    bbox = draw.textbbox((0, 0), text, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                except:
                    tw, th = 800, 100 # Fallback 

                x = (width - tw) / 2
                y = height / 2 + 150 # Pozizione in basso
                
                # Effetto Ombra / Bordo nero massiccio
                stroke_width = 4
                for dx in range(-stroke_width, stroke_width+1, 2):
                    for dy in range(-stroke_width, stroke_width+1, 2):
                        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
                
                # Testo principale Giallo
                draw.text((x, y), text, font=font, fill=(255, 230, 0, 255))
                
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
            self._generate_background(theme)
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
