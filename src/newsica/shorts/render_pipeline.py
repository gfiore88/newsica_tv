import datetime
import io
import os
import re
import subprocess
import unicodedata

import emoji
import requests
import soundfile as sf
from kokoro_onnx import Kokoro
from PIL import Image, ImageDraw, ImageFont

from newsica.audio.tts_text import prepare_text_for_tts


class ShortRenderPipeline:
    def __init__(self, *, tmp_dir: str, assets_dir: str, output_dir: str, ollama_url: str, model_name: str):
        self.tmp_dir = tmp_dir
        self.assets_dir = assets_dir
        self.output_dir = output_dir
        self.ollama_url = ollama_url
        self.model_name = model_name

        self.tmp_audio = os.path.join(tmp_dir, "short_audio.wav")
        self.tmp_srt = os.path.join(tmp_dir, "short.srt")
        self.tmp_bg = os.path.join(tmp_dir, "shorts_bg.png")

    def generate_audio(self, text: str) -> float:
        print("🎙️ Generazione audio TTS per lo Short...")
        tts_text = text.replace("#", "")
        tts_text = emoji.replace_emoji(tts_text, replace="")
        clean_text = prepare_text_for_tts(tts_text)

        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        import random

        voices = ["if_sara", "im_nicola"]
        selected_voice = random.choice(voices)
        print(f"🗣️ Voce TTS selezionata: {selected_voice}")

        samples, sample_rate = kokoro.create(clean_text, voice=selected_voice, speed=1.1, lang="it")
        sf.write(self.tmp_audio, samples, sample_rate)
        return len(samples) / sample_rate

    def generate_srt(self, text: str, duration: float):
        print("📝 Generazione file sottotitoli SRT (Character-based sync)...")
        words = text.split()
        chunks = [" ".join(words[i : i + 3]) for i in range(0, len(words), 3)]
        total_chars = sum(len(c.replace(" ", "")) for c in chunks)
        time_per_char = duration / total_chars if total_chars > 0 else 1.0

        def format_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        with open(self.tmp_srt, "w", encoding="utf-8") as f:
            current_time = 0.0
            for i, chunk in enumerate(chunks):
                start_time = current_time
                chunk_chars = len(chunk.replace(" ", ""))
                chunk_duration = chunk_chars * time_per_char
                end_time = start_time + chunk_duration
                f.write(f"{i + 1}\n")
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
                return None
            img = Image.open(io.BytesIO(response.content)).convert("RGBA")
            min_w, min_h = 400, 300
            if img.width < min_w or img.height < min_h:
                return None
            return img
        except Exception:
            return None

    def _apply_context_image_to_background(self, image: Image.Image, context_img: Image.Image):
        width, height = image.size
        box_w, box_h = 940, 680

        from PIL import ImageOps

        context_img = context_img.convert("RGBA")
        context_img = ImageOps.fit(context_img, (box_w, box_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

        radius = 40
        mask = Image.new("L", (box_w, box_h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, box_w, box_h), radius=radius, fill=215)
        context_img.putalpha(mask)

        border_thickness = 12
        card_w = box_w + (border_thickness * 2)
        card_h = box_h + (border_thickness * 2)
        card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        draw_card = ImageDraw.Draw(card)
        half_b = border_thickness // 2
        draw_card.rounded_rectangle(
            (half_b, half_b, card_w - half_b, card_h - half_b),
            radius=radius + half_b,
            outline=(255, 255, 255, 180),
            width=border_thickness,
        )
        card.alpha_composite(context_img, dest=(border_thickness, border_thickness))

        y_pos = (height - card_h) // 2 - 100
        x_pos = (width - card_w) // 2
        image.paste(card, (x_pos, y_pos), mask=card)
        return image

    def _search_pexels_image_via_llm(self, title: str):
        pexels_key = os.getenv("PEXELS_API_KEY")
        if not pexels_key:
            return None
        try:
            import urllib.parse

            prompt = f'Given the news title: "{title}". Extract a SINGLE generic English keyword that visually represents the subject (e.g. if the news is about an Italian hospital, write "hospital". If it is about police, write "police car"). Reply ONLY with the English keyword, no punctuation.'
            payload = {"model": self.model_name, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
            resp = requests.post(self.ollama_url, json=payload, timeout=10)
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
        except Exception:
            return None
        return None

    def _search_wikipedia_image_via_llm(self, title: str):
        try:
            import urllib.parse

            prompt = f'Data la notizia: "{title}". Estrai una SINGOLA entità Wikipedia (una città, un personaggio pubblico, o un oggetto generico come "Ospedale" o "Polizia"). Rispondi SOLO con il nome dell entità, niente punteggiatura.'
            payload = {"model": self.model_name, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
            resp = requests.post(self.ollama_url, json=payload, timeout=10)
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
        except Exception:
            return None
        return None

    def generate_background(self, theme: str = "news", title: str = "", image_url: str = ""):
        print(f"🎨 Generazione background verticale dinamico (tema: {theme})...")
        width, height = 1080, 1920
        base_screens_dir = os.path.join(self.assets_dir, "shorts_backgrounds", "base_screens")

        def resolve_base_screen(name: str) -> str:
            for ext in ("jpeg", "jpg", "png", "webp"):
                candidate = os.path.join(base_screens_dir, f"{name}.{ext}")
                if os.path.exists(candidate):
                    return candidate
            return ""

        base_bg_path = resolve_base_screen(theme) or resolve_base_screen("news")
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
            if not remote_url:
                remote_url = self._search_wikipedia_image_via_llm(title)
            if remote_url:
                print(f"🖼️ Immagine remota trovata: {remote_url}")
                context_img = self._download_image(remote_url)

        if context_img is not None:
            image = self._apply_context_image_to_background(image, context_img)
            print("✅ Immagine in sovraimpressione applicata con successo.")
        else:
            print("ℹ️ Nessuna immagine fornita dall'RSS. Uso solo lo sfondo tematico pulito.")

        image.save(self.tmp_bg)

    def render_video(self):
        from pilmoji import Pilmoji

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(self.output_dir, f"short_{timestamp}.mp4")
        print(f"🎬 Rendering video finale con FFmpeg verso: {output_file}...")

        subs = []
        if os.path.exists(self.tmp_srt):
            with open(self.tmp_srt, "r", encoding="utf-8") as f:
                content = f.read()
            blocks = content.strip().split("\n\n")
            for block in blocks:
                lines = block.split("\n")
                if len(lines) < 3:
                    continue
                time_line = lines[1]
                text = " ".join(lines[2:])
                m = re.match(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", time_line)
                if not m:
                    continue
                h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
                start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
                end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
                subs.append({"duration": end - start, "text": text})

        bg = Image.open(self.tmp_bg).convert("RGBA")
        width, height = bg.size

        try:
            if os.path.exists("/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 75)
            elif os.path.exists("/System/Library/Fonts/Helvetica.ttc"):
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 75)
            elif os.path.exists("/Library/Fonts/Arial.ttf"):
                font = ImageFont.truetype("/Library/Fonts/Arial.ttf", 75)
            else:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        frames_txt_path = os.path.join(self.tmp_dir, "frames.txt")
        with open(frames_txt_path, "w", encoding="utf-8") as f:
            for i, sub in enumerate(subs):
                frame_path = os.path.join(self.tmp_dir, f"frame_{i}.png")
                frame = bg.copy()
                import textwrap

                text = sub["text"].upper()
                lines = textwrap.wrap(text, width=22)
                draw = ImageDraw.Draw(frame)
                try:
                    bbox_h = draw.textbbox((0, 0), "A", font=font)
                    line_height = bbox_h[3] - bbox_h[1] + 20
                except Exception:
                    line_height = 95

                total_height = len(lines) * line_height
                start_y = (height / 2 + 150) - (total_height / 2)

                with Pilmoji(frame) as pilmoji:
                    for idx, line in enumerate(lines):
                        try:
                            bbox = draw.textbbox((0, 0), line, font=font)
                            tw = bbox[2] - bbox[0]
                            smile = emoji.emojize(":smile:")[0]
                            tw += line.count(smile) * 30
                        except Exception:
                            tw = 800

                        x = (width - tw) / 2
                        y = start_y + (idx * line_height)

                        stroke_width = 4
                        for dx in range(-stroke_width, stroke_width + 1, 2):
                            for dy in range(-stroke_width, stroke_width + 1, 2):
                                pilmoji.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
                        pilmoji.text((x, y), line, font=font, fill=(255, 230, 0, 255))

                frame.save(frame_path)
                f.write(f"file 'frame_{i}.png'\n")
                f.write(f"duration {sub['duration']:.3f}\n")
            if subs:
                f.write(f"file 'frame_{len(subs)-1}.png'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            frames_txt_path,
            "-i",
            self.tmp_audio,
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            output_file,
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"✅ Short generato con successo: {output_file}")
            return output_file
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode()
            print(f"❌ Errore FFmpeg: {error_msg}")
            raise RuntimeError(f"FFmpeg Error: {error_msg}")
