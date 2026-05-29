import datetime
import io
import os
import re
import hashlib
import subprocess
import unicodedata

import emoji
import requests
import soundfile as sf
from kokoro_onnx import Kokoro
from PIL import Image, ImageDraw, ImageFont

from newsica.audio.tts_text import prepare_text_for_tts
from newsica.generation.tts_jobs import enqueue_audio_job_and_wait, remote_generation_enabled

# ── Singleton MMS_FA: caricato una volta sola per tutto il ciclo di vita del processo ──
# La prima chiamata a _get_mms_fa_components() scarica/carica il modello (~5-10s).
# Tutte le successive trovano gli oggetti già in memoria: zero overhead aggiuntivo.
_MMS_FA_MODEL = None
_MMS_FA_TOKENIZER = None
_MMS_FA_ALIGNER = None
_MMS_FA_LABELS = None


def _get_mms_fa_components():
    """Restituisce (model, tokenizer, aligner, labels) cachati a livello di modulo."""
    global _MMS_FA_MODEL, _MMS_FA_TOKENIZER, _MMS_FA_ALIGNER, _MMS_FA_LABELS
    if _MMS_FA_MODEL is None:
        import torchaudio
        from torchaudio.pipelines import MMS_FA as _MMS_FA
        print("🔄 Caricamento MMS_FA in memoria (solo al primo short)...")
        _MMS_FA_MODEL = _MMS_FA.get_model()
        _MMS_FA_MODEL.eval()
        _MMS_FA_TOKENIZER = _MMS_FA.get_tokenizer()
        _MMS_FA_ALIGNER = _MMS_FA.get_aligner()
        _MMS_FA_LABELS = _MMS_FA.get_labels()
        print("✅ MMS_FA pronto in memoria.")
    return _MMS_FA_MODEL, _MMS_FA_TOKENIZER, _MMS_FA_ALIGNER, _MMS_FA_LABELS


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

    def generate_audio(self, text: str, theme_or_mode: str = None) -> tuple[float, str]:
        """Genera l'audio TTS e restituisce (durata_secondi, testo_pulito_effettivamente_sintetizzato).

        Il testo pulito deve essere passato a generate_srt() per garantire
        l'allineamento preciso tra parlato e sottotitoli, indipendentemente
        dalla velocità vocale di ogni personaggio.
        """
        print(f"🎙️ Generazione audio TTS per lo Short (Tema/Modo: {theme_or_mode})...")
        tts_text = text.replace("#", "")
        tts_text = emoji.replace_emoji(tts_text, replace="")
        clean_text = prepare_text_for_tts(tts_text)

        import random

        # Mappatura dei temi per diversificare le voci
        if not theme_or_mode:
            theme_or_mode = random.choice(["chiara", "maya", "leo", "giorgio", "colonnello"])
        elif theme_or_mode == "funfact":
            theme_or_mode = random.choice(["chiara", "maya", "leo", "giorgio", "colonnello"])
        elif theme_or_mode == "tech":
            theme_or_mode = "chiara"

        # Velocità dinamiche su misura per ogni conduttore negli Shorts
        speeds = {
            "chiara": 1.1,
            "news": 1.1,
            "breaking": 1.1,
            "breaking_news": 1.1,
            "maya": 0.95,
            "wellness": 0.95,
            "leo": 1.1,
            "sport": 1.1,
            "giorgio": 1.05,
            "motori": 1.05,
            "colonnello": 1.0,
            "meteo": 1.0,
        }
        selected_speed = speeds.get(theme_or_mode, 1.1)

        if remote_generation_enabled():
            ok, job = enqueue_audio_job_and_wait(
                "short_tts",
                text=clean_text,
                target_audio_path=self.tmp_audio,
                priority=120,
                title=f"Short TTS {theme_or_mode}",
                dedupe_key=f"short_tts:{hashlib.sha1(clean_text.encode('utf-8')).hexdigest()[:16]}:{theme_or_mode}",
                payload={"character": theme_or_mode, "speed": selected_speed},
                timeout_seconds=int(os.getenv("NEWSICA_SHORT_TTS_TIMEOUT_SECONDS", "180")),
            )
            if not ok:
                job_id = job.get("id") if job else "unknown"
                raise RuntimeError(f"Short TTS remoto non completato in tempo: {job_id}")
            duration = float((job.get("artifact_manifest") or {}).get("duration") or 0.0)
            if duration <= 0:
                import soundfile as sf_local

                audio_data, sample_rate = sf_local.read(self.tmp_audio)
                duration = len(audio_data) / sample_rate
            return duration, clean_text

        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        from newsica.utils.voice_helper import get_voice_style_for_character

        selected_voice = get_voice_style_for_character(kokoro, theme_or_mode)
        print(f"🗣️ Voce TTS risolta per '{theme_or_mode}'")

        samples, sample_rate = kokoro.create(clean_text, voice=selected_voice, speed=selected_speed, lang="it")
        sf.write(self.tmp_audio, samples, sample_rate)
        # Restituisce sia la durata reale dell'audio sia il testo pulito usato per la sintesi:
        # il chiamante DEVE passare clean_text a generate_srt() per garantire l'allineamento.
        return len(samples) / sample_rate, clean_text

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds % 1) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _write_srt_from_word_timings(
        path: str, word_timings: list[tuple[str, float, float]], chunk_size: int = 3
    ):
        """Scrive un file SRT raggruppando le parole in chunk da `chunk_size`.

        Args:
            path: percorso del file .srt da scrivere.
            word_timings: lista di (parola, start_sec, end_sec).
            chunk_size: quante parole per riga di sottotitolo.
        """
        fmt = ShortRenderPipeline._format_srt_time
        with open(path, "w", encoding="utf-8") as f:
            idx = 1
            for i in range(0, len(word_timings), chunk_size):
                group = word_timings[i : i + chunk_size]
                text_chunk = " ".join(w for w, _, _ in group)
                start = group[0][1]
                end = group[-1][2]
                f.write(f"{idx}\n")
                f.write(f"{fmt(start)} --> {fmt(end)}\n")
                f.write(f"{text_chunk}\n\n")
                idx += 1

    # --------------------------------------------------- forced-align via MMS_FA
    def _generate_srt_forced_align(self, text: str) -> bool:
        """Allinea `text` all'audio WAV già scritto in self.tmp_audio usando
        torchaudio MMS_FA (forced alignment multilingue, gira 100% in locale).

        Il modello viene caricato UNA SOLA VOLTA per tutto il processo (singleton
        a livello di modulo in `_get_mms_fa_components`): dal secondo short in poi
        non c'è alcun overhead di caricamento.

        Restituisce True se l'SRT è stato scritto con successo, False in caso
        di qualunque errore (il chiamante deve attivare il fallback).
        """
        try:
            import torch
            import torchaudio
            from torchaudio.pipelines import MMS_FA

            # ── 1. Carica il WAV generato da Kokoro ────────────────────────────
            waveform, sr = torchaudio.load(self.tmp_audio)
            if sr != MMS_FA.sample_rate:
                resampler = torchaudio.transforms.Resample(sr, MMS_FA.sample_rate)
                waveform = resampler(waveform)
            # MMS_FA vuole mono
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)

            # ── 2. Recupera model/tokenizer/aligner dal singleton di modulo ────
            #    Prima chiamata: carica in ~5-10s. Dalla seconda: istantaneo.
            model, tokenizer, aligner, labels = _get_mms_fa_components()

            # ── 3. Pulisci il testo: lowercase, solo caratteri nel vocabolario ─
            valid_chars = set(labels) - {'-', '*'}

            words_raw = text.lower().split()
            words_clean = []
            for w in words_raw:
                cleaned = ''.join(c for c in w if c in valid_chars)
                if cleaned:
                    words_clean.append(cleaned)

            if not words_clean:
                return False

            # ── 4. Tokenizza ──────────────────────────────────────────────────
            tokens = tokenizer(words_clean)

            # ── 5. Inferenza emissioni ────────────────────────────────────────
            with torch.inference_mode():
                emission, _ = model(waveform)

            # ── 6. Forced alignment ───────────────────────────────────────────
            word_spans = aligner(emission, tokens)  # List[List[TokenSpan]]

            # ratio: frame → secondi
            ratio = waveform.shape[-1] / MMS_FA.sample_rate / emission.shape[1]

            # ── 7. Costruisci (parola, start_sec, end_sec) ────────────────────
            word_timings: list[tuple[str, float, float]] = []
            for word, spans in zip(words_raw, word_spans):
                if not spans:
                    continue
                start_sec = spans[0].start * ratio
                end_sec = spans[-1].end * ratio
                word_timings.append((word, start_sec, end_sec))

            if not word_timings:
                return False

            self._write_srt_from_word_timings(self.tmp_srt, word_timings)
            print(f"✅ SRT forced-align scritto: {len(word_timings)} parole allineate.")
            return True

        except Exception as e:
            print(f"⚠️ Forced alignment fallito ({e}). Uso fallback character-based.")
            return False

    # ----------------------------------------------- fallback character-based
    def _generate_srt_character_based(self, text: str, duration: float):
        """Fallback: distribuisce i timing proporzionalmente ai caratteri."""
        words = text.split()
        chunks = [" ".join(words[i : i + 3]) for i in range(0, len(words), 3)]
        total_chars = sum(len(c.replace(" ", "")) for c in chunks)
        time_per_char = duration / total_chars if total_chars > 0 else 1.0

        word_timings: list[tuple[str, float, float]] = []
        current = 0.0
        for chunk in chunks:
            chunk_chars = len(chunk.replace(" ", ""))
            chunk_dur = chunk_chars * time_per_char
            word_timings.append((chunk, current, current + chunk_dur))
            current += chunk_dur

        self._write_srt_from_word_timings(self.tmp_srt, word_timings, chunk_size=1)

    # ------------------------------------------------------------------ public
    def generate_srt(self, text: str, duration: float):
        """Genera il file SRT scegliendo la strategia in base a SHORTS_FORCED_ALIGN.

        Variabile d'ambiente:
            SHORTS_FORCED_ALIGN=true   → usa MMS_FA (forced alignment parola×parola,
                                         ~1.2 GB in RAM, caricato una sola volta).
            non impostata / qualsiasi  → usa il sistema character-based (legacy,
                                         zero RAM aggiuntiva, meno preciso).

        Il forced alignment richiede che self.tmp_audio esista già (generato da
        generate_audio). Se non esiste o MMS_FA fallisce, scatta il fallback
        character-based indipendentemente dall'env.
        """
        forced_align_enabled = os.getenv("SHORTS_FORCED_ALIGN", "false").strip().lower() == "true"

        if forced_align_enabled and os.path.exists(self.tmp_audio):
            print("📝 Generazione SRT con Forced Alignment (MMS_FA) [SHORTS_FORCED_ALIGN=true]...")
            if self._generate_srt_forced_align(text):
                return
            # MMS_FA ha fallito → scatta il fallback automaticamente
        else:
            if not forced_align_enabled:
                print("📝 Generazione SRT legacy (Character-based) [SHORTS_FORCED_ALIGN non attivo]...")
        self._generate_srt_character_based(text, duration)

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
            
            from newsica.generation.tts_jobs import remote_generation_enabled, remote_llm_generate

            if remote_generation_enabled():
                keyword = remote_llm_generate(
                    prompt=prompt,
                    options={"temperature": 0.1},
                    timeout_seconds=20
                )
            else:
                payload = {"model": self.model_name, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
                resp = requests.post(self.ollama_url, json=payload, timeout=10)
                if resp.status_code == 200:
                    keyword = resp.json().get("response", "").strip()
                else:
                    keyword = ""

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
            
            from newsica.generation.tts_jobs import remote_generation_enabled, remote_llm_generate

            if remote_generation_enabled():
                entity = remote_llm_generate(
                    prompt=prompt,
                    options={"temperature": 0.1},
                    timeout_seconds=20
                )
            else:
                payload = {"model": self.model_name, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
                resp = requests.post(self.ollama_url, json=payload, timeout=10)
                if resp.status_code == 200:
                    entity = resp.json().get("response", "").strip()
                else:
                    entity = ""

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

        font = None
        candidates = [
            # macOS
            ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 75),
            ("/System/Library/Fonts/Helvetica.ttc", 75),
            ("/Library/Fonts/Arial.ttf", 75),
            # Linux (Ubuntu / Debian VPS)
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 75),
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 75),
            # Fallbacks standard Linux
            ("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 75),
        ]
        for path, font_size in candidates:
            try:
                font = ImageFont.truetype(path, size=font_size, index=1 if "Helvetica.ttc" in path else 0)
                break
            except OSError:
                continue

        if not font:
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
