import datetime
import json
import os
import queue
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from newsica.audio.music_library import MusicLibrary
from newsica.audio.music_mode import MUSIC_MODE_AI_ONLY, read_music_mode
from newsica.audio.settings import PCM_CHANNELS, PCM_CHUNK_BYTES, PCM_SAMPLE_RATE, resolve_ffmpeg_cmd


class AudioPlayout:
    def __init__(self, audio_queue, interrupt_event, is_breaking_news_active, music_library=None, ffmpeg_cmd=None):
        self.audio_queue = audio_queue
        self.interrupt_event = interrupt_event
        self.is_breaking_news_active = is_breaking_news_active
        self.music_library = music_library or MusicLibrary()
        self.ffmpeg_cmd = ffmpeg_cmd or resolve_ffmpeg_cmd()
        self.current_process = None
        self.last_music_file = None

    def _display_title_for_music_file(self, music_file):
        if not music_file:
            return ""

        track_path = Path(music_file)
        ai_sidecar_title = self._read_ai_sidecar_title(track_path)
        if ai_sidecar_title:
            return ai_sidecar_title

        artist, title = self._read_music_tags(track_path)

        if artist and title:
            return f"{artist} - {title}"

        if title:
            return title

        if track_path.parent.resolve() == self.music_library.ai_music_dir.resolve():
            return "Newsica AI Track"

        fallback_title = track_path.stem.replace("_", " ").strip()
        return " ".join(fallback_title.split())

    @staticmethod
    @lru_cache(maxsize=256)
    def _probe_music_tags(track_path_str):
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format_tags=title,artist",
                    "-of", "json",
                    track_path_str,
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            return "", ""

        if result.returncode != 0 or not result.stdout:
            return "", ""

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return "", ""

        tags = payload.get("format", {}).get("tags", {})
        artist = " ".join(str(tags.get("artist", "")).split())
        title = " ".join(str(tags.get("title", "")).split())
        return artist, title

    def _read_music_tags(self, track_path):
        if track_path.parent.resolve() == self.music_library.ai_music_dir.resolve():
            return "", ""
        return self._probe_music_tags(str(track_path))

    def _read_ai_sidecar_title(self, track_path):
        try:
            if track_path.parent.resolve() != self.music_library.ai_music_dir.resolve():
                return ""
        except Exception:
            return ""

        metadata_file = track_path.with_suffix(".json")
        try:
            payload = json.loads(metadata_file.read_text(encoding="utf-8"))
        except Exception:
            return ""

        title = " ".join(str(payload.get("title", "")).split())
        return title

    def build_music_metadata(self, music_file, current_state=None):
        state = dict(current_state or {})
        state["current_music_title"] = self._display_title_for_music_file(music_file)
        return state

    def is_interrupted(self):
        return self.interrupt_event.is_set() or self.is_breaking_news_active()

    def clear_queue(self):
        cleared = 0
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
                cleared += 1
            except queue.Empty:
                break
        return cleared

    def stop_current_process(self, reason=""):
        process = self.current_process
        if not process:
            return

        if reason:
            print(reason)
        try:
            process.terminate()
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=1)
            except Exception as e:
                print(f"⚠️ Errore kill processo audio corrente: {e}")
        except Exception as e:
            print(f"⚠️ Errore terminazione processo audio corrente: {e}")
        finally:
            self.current_process = None

    def queue_item(self, item):
        while True:
            if self.is_interrupted():
                return False
            try:
                self.audio_queue.put(item, timeout=0.5)
                return True
            except queue.Full:
                continue

    def _pcm_decode_command(self, audio_file):
        return [
            self.ffmpeg_cmd,
            "-hide_banner",
            "-loglevel", "error",
            "-i", audio_file,
            "-f", "s16le",
            "-ar", str(PCM_SAMPLE_RATE),
            "-ac", str(PCM_CHANNELS),
            "pipe:1",
        ]

    def _music_decode_command(self, music_file):
        return [
            self.ffmpeg_cmd,
            "-hide_banner",
            "-loglevel", "error",
            "-i", music_file,
            "-vn",
            "-filter:a", "volume=1.2,afade=t=in:ss=0:d=2.5",
            "-f", "s16le",
            "-ar", str(PCM_SAMPLE_RATE),
            "-ac", str(PCM_CHANNELS),
            "pipe:1",
        ]

    def _mix_command(self, music_file, voice_file):
        return [
            self.ffmpeg_cmd,
            "-y",
            "-i", voice_file,
            "-i", music_file,
            "-filter_complex",
            "[0:a]apad=pad_len=72000,volume=2.6,asplit=2[v_main][v_side]; "
            "[1:a]volume=0.25[m]; "
            "[m][v_side]sidechaincompress=threshold=0.03:ratio=20:attack=50:release=1000[music]; "
            "[v_main][music]amix=inputs=2:duration=first:dropout_transition=0",
            "-f", "s16le",
            "-ar", str(PCM_SAMPLE_RATE),
            "-ac", str(PCM_CHANNELS),
            "pipe:1",
        ]

    def _ensure_music_allowed_by_mode(self, music_file):
        if not music_file:
            return None

        mode = read_music_mode()
        if mode != MUSIC_MODE_AI_ONLY:
            return music_file

        try:
            music_path = Path(music_file).resolve()
            ai_music_dir = self.music_library.ai_music_dir.resolve()
            if music_path.is_relative_to(ai_music_dir):
                return music_file
        except Exception:
            pass

        replacement = self.get_random_music(exclude=self.last_music_file)
        if replacement:
            print(
                "🎵 Modalità Solo Musica AI: sostituisco brano non AI "
                f"({os.path.basename(str(music_file))}) con {os.path.basename(str(replacement))}."
            )
            return replacement

        print(
            "⚠️ Modalità Solo Musica AI attiva, ma nessun brano valido "
            "trovato in assets/ai_music."
        )
        return None

    def queue_pcm_from_file(self, audio_file, block_info=None, is_breaking_news=False):
        if block_info:
            self.audio_queue.put({"type": "metadata", "state": block_info})

        process = subprocess.Popen(self._pcm_decode_command(audio_file), stdout=subprocess.PIPE)
        if not is_breaking_news:
            self.current_process = process

        count = 0
        while True:
            if not is_breaking_news and self.is_interrupted():
                print("⏭️ Interrompo il caricamento audio regolare.")
                process.terminate()
                break

            data = process.stdout.read(PCM_CHUNK_BYTES)
            if not data:
                break
            if not is_breaking_news:
                if not self.queue_item({"type": "audio", "data": data}):
                    process.terminate()
                    break
            else:
                self.audio_queue.put({"type": "audio", "data": data})
            count += 1

        process.wait()
        if not is_breaking_news:
            self.current_process = None
        print(f"✅ Audio voce caricato nella coda ({count} chunks).")

    def queue_jingle(self, jingle_file, label="jingle"):
        if not os.path.exists(jingle_file):
            print(f"⚠️ Jingle non trovato: {jingle_file}")
            return True

        print(f"🎶 Lancio {label}: {os.path.basename(jingle_file)}")
        process = subprocess.Popen(self._pcm_decode_command(jingle_file), stdout=subprocess.PIPE)
        self.current_process = process

        while True:
            if self.is_interrupted():
                print(f"⏭️ Interrompo {label}.")
                process.terminate()
                break

            data = process.stdout.read(PCM_CHUNK_BYTES)
            if not data:
                break
            if not self.queue_item({"type": "audio", "data": data}):
                process.terminate()
                break

        process.wait()
        self.current_process = None
        return not self.is_interrupted()

    def mix_and_queue(self, music_file, voice_file, block_info=None):
        music_file = self._ensure_music_allowed_by_mode(music_file)
        if not music_file:
            return self.queue_pcm_from_file(voice_file, block_info)

        print(f"Mixaggio in corso: Voce + {os.path.basename(music_file)}")

        if block_info:
            self.audio_queue.put({"type": "metadata", "state": block_info})

        process = subprocess.Popen(self._mix_command(music_file, voice_file), stdout=subprocess.PIPE)
        self.current_process = process

        # Legge l'intero audio in memoria per applicare il fade-out software finale
        chunks = []
        while True:
            if self.is_interrupted():
                process.terminate()
                break
            data = process.stdout.read(PCM_CHUNK_BYTES)
            if not data:
                break
            chunks.append(data)

        process.wait()
        self.current_process = None

        if self.is_interrupted() or not chunks:
            print("⏭️ Interrompo o nessun chunk generato.")
            return

        # Applica fade-out software lineare sugli ultimi 30 chunk (circa 2.5 secondi)
        import numpy as np
        fade_chunks = min(30, len(chunks))
        for idx in range(fade_chunks):
            chunk_idx = len(chunks) - fade_chunks + idx
            data = chunks[chunk_idx]
            
            samples = np.frombuffer(data, dtype=np.int16).copy()
            start_factor = (fade_chunks - idx) / fade_chunks
            end_factor = (fade_chunks - idx - 1) / fade_chunks
            factors = np.linspace(start_factor, end_factor, len(samples))
            
            chunks[chunk_idx] = (samples * factors).astype(np.int16).tobytes()

        # Inserisce i chunk nella coda
        print(f"Caricamento di {len(chunks)} chunk audio con fade-out finale nella coda...")
        count = 0
        for data in chunks:
            if self.is_interrupted():
                break
            if not self.queue_item({"type": "audio", "data": data}):
                break
            count += 1

        print(f"✅ Blocco audio caricato nella coda ({count} chunks).")

    def get_random_music(self, exclude=None):
        return self.music_library.get_random_track(exclude=exclude)

    def queue_music_track(self, deadline):
        if datetime.datetime.now() >= deadline or self.is_interrupted():
            return

        music_file = self.get_random_music(exclude=self.last_music_file)
        if not music_file:
            time.sleep(1)
            return
        music_file = self._ensure_music_allowed_by_mode(music_file)
        if not music_file:
            time.sleep(1)
            return
        self.last_music_file = music_file
        self.audio_queue.put(
            {
                "type": "metadata",
                "state": self.build_music_metadata(music_file),
            }
        )

        print(f"🎵 Brano musicale di riempimento: {os.path.basename(music_file)}")
        process = subprocess.Popen(self._music_decode_command(music_file), stdout=subprocess.PIPE)
        self.current_process = process

        import numpy as np
        fade_duration = 2.5
        
        while True:
            now = datetime.datetime.now()
            if now >= deadline:
                break
                
            if self.is_interrupted():
                process.terminate()
                break

            data = process.stdout.read(PCM_CHUNK_BYTES)
            if not data:
                break
                
            time_left = (deadline - now).total_seconds()
            if time_left < fade_duration:
                # Applica fade-out lineare sugli ultimi secondi
                factor = max(0.0, time_left / fade_duration)
                samples = np.frombuffer(data, dtype=np.int16).copy()
                data = (samples * factor).astype(np.int16).tobytes()

            if not self.queue_item({"type": "audio", "data": data}):
                process.terminate()
                break

        if process.poll() is None:
            process.terminate()
        process.wait()
        self.current_process = None

    def queue_single_music_track(self, music_file=None):
        if self.is_interrupted():
            return

        if not music_file:
            music_file = self.get_random_music(exclude=self.last_music_file)
        if not music_file:
            time.sleep(1)
            return
        music_file = self._ensure_music_allowed_by_mode(music_file)
        if not music_file:
            time.sleep(1)
            return
        self.last_music_file = music_file
        self.audio_queue.put(
            {
                "type": "metadata",
                "state": self.build_music_metadata(music_file),
            }
        )

        print(f"🎵 Brano musicale intermedio (Full Track): {os.path.basename(music_file)}")
        process = subprocess.Popen(self._music_decode_command(music_file), stdout=subprocess.PIPE)
        self.current_process = process

        while True:
            if self.is_interrupted():
                process.terminate()
                break

            data = process.stdout.read(PCM_CHUNK_BYTES)
            if not data:
                break
            if not self.queue_item({"type": "audio", "data": data}):
                process.terminate()
                break

        if process.poll() is None:
            process.terminate()
        process.wait()
        self.current_process = None
