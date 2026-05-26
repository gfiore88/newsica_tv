import datetime
import json
import os
import queue
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from newsica.audio.music_library import MusicLibrary
from newsica.storage.repositories.chat_music_requests_repository import consume_next_ready_request
from newsica.audio.music_mode import MUSIC_MODE_AI_ONLY, read_music_mode
from newsica.audio.settings import PCM_CHANNELS, PCM_CHUNK_BYTES, PCM_SAMPLE_RATE, resolve_ffmpeg_cmd
from newsica.config.paths import BASE_DIR, TMP_DIR

import numpy as np
from newsica.broadcast.runtime_state import get_current_state

class PlayoutSidechainDucker:
    def __init__(self, sample_rate=24000):
        self.threshold = 0.012
        self.ratio = 20.0
        chunk_dur = 2048.0 / float(sample_rate)
        
        self.attack_coef = 1.0 - np.exp(-chunk_dur / 0.05)
        self.release_coef = 1.0 - np.exp(-chunk_dur / 0.8)
        
        self.envelope = 0.0
        self.current_gain = 1.0      # Guadagno normale della traccia musicale
        self.normal_gain = 1.0
        self.min_gain = 0.08         # Abbassa la musica all'8% del volume
        self.overlay_volume = 1.55   # Boost della voce per chiarezza

    def mix(self, base_chunk, voice_chunk):
        min_len = min(len(base_chunk), len(voice_chunk))
        if min_len == 0:
            return base_chunk
            
        base = np.frombuffer(base_chunk[:min_len], dtype=np.int16).astype(np.float32)
        overlay = np.frombuffer(voice_chunk[:min_len], dtype=np.int16).astype(np.float32)
        
        # Calcola il picco
        voice_peak = np.max(np.abs(overlay)) / 32768.0
        
        # Aggiorna l'inviluppo
        if voice_peak > self.envelope:
            self.envelope += self.attack_coef * (voice_peak - self.envelope)
        else:
            self.envelope += self.release_coef * (voice_peak - self.envelope)
            
        # Calcola il gain di sidechain basato sulla compressione
        if self.envelope > self.threshold:
            env_clamped = max(self.envelope, 1e-5)
            input_db = 20.0 * np.log10(env_clamped)
            thresh_db = 20.0 * np.log10(self.threshold)
            over_db = input_db - thresh_db
            attenuation_db = over_db * (1.0 - 1.0 / self.ratio)
            target_gain_factor = 10.0 ** (-attenuation_db / 20.0)
            target_gain = self.min_gain + (self.normal_gain - self.min_gain) * target_gain_factor
            target_gain = min(target_gain, self.normal_gain)
        else:
            target_gain = self.normal_gain
            
        gains = np.linspace(self.current_gain, target_gain, len(base), dtype=np.float32)
        self.current_gain = target_gain
        
        mixed = (base * gains) + (overlay * self.overlay_volume)
        return np.clip(mixed, -32768, 32767).astype(np.int16).tobytes()


def _prepare_telegram_voice_for_air(input_file, output_file):
    try:
        cmd = [
            resolve_ffmpeg_cmd(),
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(input_file),
            "-af",
            (
                "highpass=f=100,"
                "lowpass=f=7000,"
                "acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=3,"
                "loudnorm=I=-18:TP=-1.5:LRA=7"
            ),
            "-ar", "24000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(output_file),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"⚠️ Normalizzazione vocale Telegram fallita, uso file originale: {e}")
        return False

def _generate_request_announcement(author, title, output_file):
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
        
        onnx_path = BASE_DIR / "kokoro-v1.0.onnx"
        voices_path = BASE_DIR / "voices-v1.0.bin"
        
        # Pulisce i caratteri speciali per la sintesi vocale
        clean_title = title.replace('"', '').replace("'", "").strip()
        clean_author = author.replace('"', '').replace("'", "").strip()
        
        text = f"Newsica ti ascolta! Questo brano, {clean_title}, è stato richiesto da {clean_author}."
        print(f"🎙️ Generazione annuncio richiesta chat TTS: \"{text}\"")
        
        kokoro = Kokoro(str(onnx_path), str(voices_path))
        samples, sample_rate = kokoro.create(
            text, voice="if_sara", speed=0.95, lang="it"
        )
        sf.write(output_file, samples, sample_rate)
        print(f"✅ Annuncio richiesta generato con successo: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Errore durante la generazione dell'annuncio richiesta TTS: {e}")
        return False


def _generate_telegram_announcement(author, output_file):
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
        
        onnx_path = BASE_DIR / "kokoro-v1.0.onnx"
        voices_path = BASE_DIR / "voices-v1.0.bin"
        
        clean_author = author.replace('"', '').replace("'", "").strip()
        
        text = f"E ora diamo voce a voi! Ecco un messaggio vocale inviato da {clean_author} su Telegram."
        print(f"🎙️ Generazione annuncio vocale Telegram TTS: \"{text}\"")
        
        kokoro = Kokoro(str(onnx_path), str(voices_path))
        samples, sample_rate = kokoro.create(
            text, voice="if_sara", speed=0.95, lang="it"
        )
        sf.write(output_file, samples, sample_rate)
        print(f"✅ Annuncio vocale Telegram generato con successo: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Errore durante la generazione dell'annuncio vocale Telegram TTS: {e}")
        return False


class AudioPlayout:
    def __init__(self, audio_queue, interrupt_event, is_breaking_news_active, music_library=None, ffmpeg_cmd=None):
        self.audio_queue = audio_queue
        self.interrupt_event = interrupt_event
        self.is_breaking_news_active = is_breaking_news_active
        self.music_library = music_library or MusicLibrary()
        self.ffmpeg_cmd = ffmpeg_cmd or resolve_ffmpeg_cmd()
        self.current_process = None
        self.last_music_file = None

    def _consume_requested_track(self):
        request = consume_next_ready_request()
        if not request:
            return None

        audio_path = request.get("audio_path")
        if not audio_path or not Path(audio_path).exists():
            print(
                f"⚠️ Richiesta musicale {request.get('id')} pronta ma senza file valido: {audio_path}"
            )
            return None

        print(
            f"🎵 [CHAT REQUEST] Il prossimo brano sara' una richiesta della chat: "
            f"{os.path.basename(audio_path)}"
        )
        return audio_path

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

    def build_post_telegram_restore_metadata(self, previous_state, bg_music=None):
        restored = dict(previous_state or {})
        if bg_music:
            restored = self.build_music_metadata(bg_music, current_state=restored)
        restored["requested_by"] = ""
        restored["requested_title"] = ""
        return restored

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

    def _safe_wait(self, process, name="process", timeout=3.0):
        if not process:
            return
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"⚠️ Timeout scaduto durante wait su '{name}', forzo la terminazione.")
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                print(f"⚠️ Timeout scaduto anche su terminate per '{name}', forzo kill.")
                try:
                    process.kill()
                    process.wait(timeout=1.0)
                except Exception:
                    pass
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️ Eccezione durante wait su '{name}': {e}")

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

    def _ai_track_matches_theme(self, music_file, theme):
        if not music_file or not theme:
            return False
        try:
            track_path = Path(music_file)
            metadata_file = track_path.with_suffix(".json")
            if not metadata_file.exists():
                return False
            with metadata_file.open("r", encoding="utf-8") as f:
                meta = json.load(f)
            track_theme = meta.get("theme")
            if not track_theme:
                return False
            return " ".join(str(track_theme).lower().strip().split()) == " ".join(theme.lower().strip().split())
        except Exception:
            return False

    def _ensure_music_allowed_by_mode(self, music_file):
        if not music_file:
            return None

        # Recuperiamo il tema dello show attivo dallo stato per decidere sul playout
        theme = None
        try:
            from newsica.broadcast.runtime_state import get_current_state
            theme = get_current_state().get("theme")
        except Exception:
            pass

        mode = read_music_mode()
        # Se è programmato un tema, forziamo la modalità Solo AI per questo brano
        if theme:
            mode = MUSIC_MODE_AI_ONLY

        if mode != MUSIC_MODE_AI_ONLY:
            return music_file

        is_valid_ai = False
        try:
            music_path = Path(music_file).resolve()
            ai_music_dir = self.music_library.ai_music_dir.resolve()
            if music_path.is_relative_to(ai_music_dir):
                is_valid_ai = True
        except Exception:
            pass

        # Se abbiamo un tema, dobbiamo anche verificare che la traccia AI corrisponda al tema
        if is_valid_ai and theme:
            if not self._ai_track_matches_theme(music_file, theme):
                is_valid_ai = False

        if is_valid_ai:
            return music_file

        replacement = None
        ai_candidates = self.music_library._scan(self.music_library.ai_music_dir)
        ai_candidates = [path for path in ai_candidates if str(path) != self.last_music_file]
        if theme:
            ai_candidates = [path for path in ai_candidates if self._ai_track_matches_theme(str(path), theme)]
        candidates_with_metadata = [path for path in ai_candidates if path.with_suffix(".json").exists()]
        if candidates_with_metadata:
            ai_candidates = candidates_with_metadata
        if ai_candidates:
            replacement = str(ai_candidates[0])
        if replacement:
            label_text = f"per il tema '{theme}'" if theme else "non AI"
            print(
                f"🎵 Sostituisco brano non conforme {label_text} "
                f"({os.path.basename(str(music_file))}) con {os.path.basename(str(replacement))}."
            )
            return replacement

        print(
            f"⚠️ Modalità Solo AI attiva (tema: '{theme}'), ma nessun brano valido "
            "trovato in assets/ai_music. Mando in onda il brano originale come estremo fallback."
        )
        return music_file

    def queue_pcm_from_file(self, audio_file, block_info=None, is_breaking_news=False):
        if block_info:
            self.audio_queue.put({"type": "metadata", "state": block_info})

        process = subprocess.Popen(
            self._pcm_decode_command(audio_file),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
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

        self._safe_wait(process, name="pcm_decode_process", timeout=3.0)
        if not is_breaking_news:
            self.current_process = None
        print(f"✅ Audio voce caricato nella coda ({count} chunks).")

    def queue_jingle(self, jingle_file, label="jingle"):
        if not os.path.exists(jingle_file):
            print(f"⚠️ Jingle non trovato: {jingle_file}")
            return True

        print(f"🎶 Lancio {label}: {os.path.basename(jingle_file)}")
        process = subprocess.Popen(
            self._pcm_decode_command(jingle_file),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
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

        self._safe_wait(process, name="jingle_process", timeout=3.0)
        self.current_process = None
        return not self.is_interrupted()

    def mix_and_queue(self, music_file, voice_file, block_info=None):
        music_file = self._ensure_music_allowed_by_mode(music_file)
        if not music_file:
            return self.queue_pcm_from_file(voice_file, block_info)

        print(f"Mixaggio in corso: Voce + {os.path.basename(music_file)}")

        if block_info:
            self.audio_queue.put({"type": "metadata", "state": block_info})

        process = subprocess.Popen(
            self._mix_command(music_file, voice_file),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
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

        self._safe_wait(process, name="mix_and_queue_process", timeout=3.0)
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

    def get_random_music(self, exclude=None, theme=None):
        if theme is None:
            try:
                from newsica.broadcast.runtime_state import get_current_state
                theme = get_current_state().get("theme")
            except Exception:
                pass
        return self.music_library.get_random_track(exclude=exclude, theme=theme)

    def queue_music_track(self, deadline):
        if isinstance(deadline, str):
            deadline = datetime.datetime.fromisoformat(deadline)
            
        if datetime.datetime.now() >= deadline or self.is_interrupted():
            return

        # 1. Controlla prima se c'è un vocale Telegram approvato
        try:
            from newsica.storage.repositories.telegram_repository import consume_next_approved_voice, mark_played
            tg_voice = consume_next_approved_voice()
        except Exception as e:
            print(f"⚠️ Errore durante il recupero dei vocali Telegram: {e}")
            tg_voice = None

        if tg_voice:
            voice_file = tg_voice.get("converted_path")
            author_display = tg_voice.get("author_first_name", "un ascoltatore")
            if tg_voice.get("author_username"):
                author_display = f"{author_display} (@{tg_voice['author_username']})"
                
            if voice_file and os.path.exists(voice_file):
                print(f"🎙️ [TELEGRAM VOICE] In onda il vocale di {author_display}")
                previous_state = get_current_state()
                normalized_voice_file = TMP_DIR / f"tg_voice_normalized_{tg_voice['id']}.wav"
                playback_voice_file = str(normalized_voice_file)
                if not _prepare_telegram_voice_for_air(voice_file, playback_voice_file):
                    playback_voice_file = str(voice_file)
                
                # Sottofondo musicale per il vocale
                bg_music = self.get_random_music(exclude=self.last_music_file)
                if not bg_music:
                    print("⚠️ Nessun sottofondo musicale trovato per il vocale Telegram. Lo riproduco liscio.")
                    self.queue_pcm_from_file(playback_voice_file, {
                        "status": "ON_AIR",
                        "current_block": "telegram_voice",
                        "current_title": f"Vocale Telegram di {author_display}",
                        "current_music_title": f"Vocale Telegram di {author_display}",
                        "requested_by": author_display,
                        "requested_title": "Messaggio Vocale"
                    })
                    self.audio_queue.put(
                        {
                            "type": "metadata",
                            "state": self.build_post_telegram_restore_metadata(previous_state),
                        }
                    )
                    try:
                        mark_played(tg_voice["id"])
                    except Exception:
                        pass
                    return

                # Generazione dell'annuncio
                announcement_file = TMP_DIR / "tg_announcement.wav"
                has_announcement = _generate_telegram_announcement(author_display, announcement_file)
                
                metadata = {
                    "current_music_title": f"Vocale Telegram di {author_display}",
                    "requested_by": author_display,
                    "requested_title": "Messaggio Vocale",
                    "current_block": "telegram_voice",
                    "current_title": f"Vocale Telegram di {author_display}",
                }
                self.audio_queue.put({"type": "metadata", "state": metadata})
                
                # Decodifichiamo l'annuncio e il vocale
                voice_files_to_play = []
                if has_announcement:
                    voice_files_to_play.append(str(announcement_file))
                voice_files_to_play.append(playback_voice_file)
                
                # Processo di riproduzione con musica + sidechain
                print(f"🎵 Sottofondo musicale: {os.path.basename(bg_music)}")
                process = subprocess.Popen(
                    self._music_decode_command(bg_music),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                self.current_process = process
                
                ducker = PlayoutSidechainDucker(PCM_SAMPLE_RATE)
                current_voice_idx = 0
                active_voice_proc = None
                
                try:
                    while True:
                        if self.is_interrupted():
                            process.terminate()
                            break
                            
                        data = process.stdout.read(PCM_CHUNK_BYTES)
                        if not data:
                            break
                            
                        # Gestione della catena di audio vocali (TTS prima, poi il vocale utente)
                        if current_voice_idx < len(voice_files_to_play):
                            if active_voice_proc is None:
                                active_voice_file = voice_files_to_play[current_voice_idx]
                                active_voice_proc = subprocess.Popen(
                                    self._pcm_decode_command(active_voice_file),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL,
                                )
                                
                            voice_data = active_voice_proc.stdout.read(len(data))
                            if voice_data:
                                data = ducker.mix(data, voice_data)
                            else:
                                print(f"🎙️ [TELEGRAM SIDECHAIN] Fine lettura vocale indice {current_voice_idx}, attesa processo...")
                                self._safe_wait(active_voice_proc, name=f"tg_voice_active_proc_{current_voice_idx}", timeout=2.0)
                                active_voice_proc = None
                                current_voice_idx += 1
                                print(f"🎙️ [TELEGRAM SIDECHAIN] Passaggio al vocale indice {current_voice_idx}")
                        elif ducker.current_gain < 0.99:
                            # Sfumatura di rilascio finale
                            silence_chunk = b"\x00" * len(data)
                            data = ducker.mix(data, silence_chunk)
                        else:
                            # Quando sia l'annuncio che il vocale sono terminati, terminiamo la riproduzione di questo sottofondo
                            print("🎙️ [TELEGRAM SIDECHAIN] Annuncio e vocale terminati, ripristino volume completato. Esco dal loop.")
                            break
                            
                        if not self.queue_item({"type": "audio", "data": data}):
                            print("⚠️ [TELEGRAM SIDECHAIN] Interruzione coda piena o errore queue_item. Esco dal loop.")
                            process.terminate()
                            break
                finally:
                    if active_voice_proc:
                        print("🎙️ [TELEGRAM SIDECHAIN] Pulizia active_voice_proc in corso...")
                        try:
                            active_voice_proc.stdout.close()
                            active_voice_proc.terminate()
                            self._safe_wait(active_voice_proc, name="tg_voice_cleanup", timeout=0.2)
                        except Exception:
                            pass
                    if process.poll() is None:
                        print("🎵 [TELEGRAM SIDECHAIN] Termino processo sottofondo musicale...")
                        try:
                            process.stdout.close()
                        except Exception:
                            pass
                        process.terminate()
                    self._safe_wait(process, name="tg_bg_music", timeout=0.2)
                    self.current_process = None
                    try:
                        mark_played(tg_voice["id"])
                    except Exception:
                        pass
                    if str(normalized_voice_file) != str(voice_file) and normalized_voice_file.exists():
                        try:
                            normalized_voice_file.unlink()
                        except Exception:
                            pass
                    self.audio_queue.put(
                        {
                            "type": "metadata",
                            "state": self.build_post_telegram_restore_metadata(previous_state, bg_music),
                        }
                    )
                    
                # Procediamo oltre, interrompendo il brano per far posto alla programmazione
                return

        request = consume_next_ready_request()
        music_file = None
        is_requested = False
        if request:
            music_file = request.get("audio_path")
            if music_file and Path(music_file).exists():
                is_requested = True
                print(
                    f"🎵 [CHAT REQUEST] Il prossimo brano sara' una richiesta della chat: "
                    f"{os.path.basename(music_file)}"
                )
            else:
                if music_file:
                    print(f"⚠️ Richiesta musicale {request.get('id')} pronta ma senza file valido: {music_file}")
                music_file = None

        if not music_file:
            music_file = self.get_random_music(exclude=self.last_music_file)
            
        if not music_file:
            time.sleep(1)
            return
        if not str(Path(music_file).name).startswith("ai_track_request_"):
            music_file = self._ensure_music_allowed_by_mode(music_file)
        if not music_file:
            time.sleep(1)
            return
            
        self.last_music_file = music_file
        
        metadata = self.build_music_metadata(music_file)
        
        # Gestione Annuncio Vocale in Sidechain
        voice_proc = None
        ducker = None
        if is_requested and request:
            metadata["requested_by"] = request.get("author", "Anonimo")
            metadata["requested_title"] = metadata.get("current_music_title") or request.get("generated_title") or "Brano Richiesto"
            
            announcement_file = TMP_DIR / "request_announcement.wav"
            if _generate_request_announcement(metadata["requested_by"], metadata["requested_title"], announcement_file):
                voice_proc = subprocess.Popen(
                    self._pcm_decode_command(str(announcement_file)),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                ducker = PlayoutSidechainDucker(PCM_SAMPLE_RATE)
        else:
            metadata["requested_by"] = ""
            metadata["requested_title"] = ""

        self.audio_queue.put(
            {
                "type": "metadata",
                "state": metadata,
            }
        )

        print(f"🎵 Brano musicale di riempimento: {os.path.basename(music_file)}")
        process = subprocess.Popen(
            self._music_decode_command(music_file),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.current_process = process

        import numpy as np
        fade_duration = 2.5
        
        try:
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
                    
                # Applica mix sidechain con l'annuncio vocale se attivo
                if voice_proc:
                    voice_data = voice_proc.stdout.read(len(data))
                    if voice_data:
                        data = ducker.mix(data, voice_data)
                    else:
                        voice_proc.wait()
                        voice_proc = None
                elif ducker and ducker.current_gain < 0.99:
                    # Dissolvenza di rilascio post-annuncio per ripristinare il volume della musica
                    silence_chunk = b"\x00" * len(data)
                    data = ducker.mix(data, silence_chunk)

                time_left = (deadline - now).total_seconds()
                if time_left < fade_duration:
                    # Applica fade-out lineare sugli ultimi secondi
                    factor = max(0.0, time_left / fade_duration)
                    samples = np.frombuffer(data, dtype=np.int16).copy()
                    data = (samples * factor).astype(np.int16).tobytes()

                if not self.queue_item({"type": "audio", "data": data}):
                    process.terminate()
                    break
        finally:
            if voice_proc:
                try:
                    voice_proc.stdout.close()
                    voice_proc.terminate()
                    self._safe_wait(voice_proc, name="announcement_cleanup", timeout=0.2)
                except Exception:
                    pass

        if process.poll() is None:
            try:
                process.stdout.close()
            except Exception:
                pass
            process.terminate()
        self._safe_wait(process, name="music_track_process", timeout=0.2)
        self.current_process = None

    def queue_single_music_track(self, music_file=None):
        if self.is_interrupted():
            return

        # 1. Controlla prima se c'è un vocale Telegram approvato
        try:
            from newsica.storage.repositories.telegram_repository import consume_next_approved_voice, mark_played
            tg_voice = consume_next_approved_voice()
        except Exception as e:
            print(f"⚠️ Errore durante il recupero dei vocali Telegram: {e}")
            tg_voice = None

        if tg_voice:
            voice_file = tg_voice.get("converted_path")
            author_display = tg_voice.get("author_first_name", "un ascoltatore")
            if tg_voice.get("author_username"):
                author_display = f"{author_display} (@{tg_voice['author_username']})"
                
            if voice_file and os.path.exists(voice_file):
                print(f"🎙️ [TELEGRAM VOICE] In onda il vocale di {author_display}")
                previous_state = get_current_state()
                normalized_voice_file = TMP_DIR / f"tg_voice_normalized_{tg_voice['id']}.wav"
                playback_voice_file = str(normalized_voice_file)
                if not _prepare_telegram_voice_for_air(voice_file, playback_voice_file):
                    playback_voice_file = str(voice_file)
                
                # Sottofondo musicale per il vocale
                bg_music = self.get_random_music(exclude=self.last_music_file)
                if not bg_music:
                    print("⚠️ Nessun sottofondo musicale trovato per il vocale Telegram. Lo riproduco liscio.")
                    self.queue_pcm_from_file(playback_voice_file, {
                        "status": "ON_AIR",
                        "current_block": "telegram_voice",
                        "current_title": f"Vocale Telegram di {author_display}",
                        "current_music_title": f"Vocale Telegram di {author_display}",
                        "requested_by": author_display,
                        "requested_title": "Messaggio Vocale"
                    })
                    self.audio_queue.put(
                        {
                            "type": "metadata",
                            "state": self.build_post_telegram_restore_metadata(previous_state),
                        }
                    )
                    try:
                        mark_played(tg_voice["id"])
                    except Exception:
                        pass
                    return

                # Generazione dell'annuncio
                announcement_file = TMP_DIR / "tg_announcement.wav"
                has_announcement = _generate_telegram_announcement(author_display, announcement_file)
                
                metadata = {
                    "current_music_title": f"Vocale Telegram di {author_display}",
                    "requested_by": author_display,
                    "requested_title": "Messaggio Vocale",
                    "current_block": "telegram_voice",
                    "current_title": f"Vocale Telegram di {author_display}",
                }
                self.audio_queue.put({"type": "metadata", "state": metadata})
                
                # Decodifichiamo l'annuncio e il vocale
                voice_files_to_play = []
                if has_announcement:
                    voice_files_to_play.append(str(announcement_file))
                voice_files_to_play.append(playback_voice_file)
                
                # Processo di riproduzione con musica + sidechain
                print(f"🎵 Sottofondo musicale: {os.path.basename(bg_music)}")
                process = subprocess.Popen(
                    self._music_decode_command(bg_music),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                self.current_process = process
                
                ducker = PlayoutSidechainDucker(PCM_SAMPLE_RATE)
                current_voice_idx = 0
                active_voice_proc = None
                
                try:
                    while True:
                        if self.is_interrupted():
                            process.terminate()
                            break
                            
                        data = process.stdout.read(PCM_CHUNK_BYTES)
                        if not data:
                            break
                            
                        # Gestione della catena di audio vocali (TTS prima, poi il vocale utente)
                        if current_voice_idx < len(voice_files_to_play):
                            if active_voice_proc is None:
                                active_voice_file = voice_files_to_play[current_voice_idx]
                                active_voice_proc = subprocess.Popen(
                                    self._pcm_decode_command(active_voice_file),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL,
                                )
                                
                            voice_data = active_voice_proc.stdout.read(len(data))
                            if voice_data:
                                data = ducker.mix(data, voice_data)
                            else:
                                print(f"🎙️ [TELEGRAM SINGLE SIDECHAIN] Fine lettura vocale indice {current_voice_idx}, attesa processo...")
                                self._safe_wait(active_voice_proc, name=f"tg_single_voice_active_proc_{current_voice_idx}", timeout=2.0)
                                active_voice_proc = None
                                current_voice_idx += 1
                                print(f"🎙️ [TELEGRAM SINGLE SIDECHAIN] Passaggio al vocale indice {current_voice_idx}")
                        elif ducker.current_gain < 0.99:
                            # Sfumatura di rilascio finale
                            silence_chunk = b"\x00" * len(data)
                            data = ducker.mix(data, silence_chunk)
                        else:
                            # Quando sia l'annuncio che il vocale sono terminati, terminiamo la riproduzione di questo sottofondo
                            print("🎙️ [TELEGRAM SINGLE SIDECHAIN] Annuncio e vocale terminati, ripristino volume completato. Esco dal loop.")
                            break
                            
                        if not self.queue_item({"type": "audio", "data": data}):
                            print("⚠️ [TELEGRAM SINGLE SIDECHAIN] Interruzione coda piena o errore queue_item. Esco dal loop.")
                            process.terminate()
                            break
                finally:
                    if active_voice_proc:
                        print("🎙️ [TELEGRAM SINGLE SIDECHAIN] Pulizia active_voice_proc in corso...")
                        try:
                            active_voice_proc.stdout.close()
                            active_voice_proc.terminate()
                            self._safe_wait(active_voice_proc, name="tg_single_voice_cleanup", timeout=0.2)
                        except Exception:
                            pass
                    if process.poll() is None:
                        print("🎵 [TELEGRAM SINGLE SIDECHAIN] Termino processo sottofondo musicale...")
                        try:
                            process.stdout.close()
                        except Exception:
                            pass
                        process.terminate()
                    self._safe_wait(process, name="tg_single_bg_music", timeout=0.2)
                    self.current_process = None
                    try:
                        mark_played(tg_voice["id"])
                    except Exception:
                        pass
                    if str(normalized_voice_file) != str(voice_file) and normalized_voice_file.exists():
                        try:
                            normalized_voice_file.unlink()
                        except Exception:
                            pass
                    self.audio_queue.put(
                        {
                            "type": "metadata",
                            "state": self.build_post_telegram_restore_metadata(previous_state, bg_music),
                        }
                    )
                    
                # Procediamo oltre
                return

        request = consume_next_ready_request()
        is_requested = False
        if request:
            music_file = request.get("audio_path")
            if music_file and Path(music_file).exists():
                is_requested = True
                print(
                    f"🎵 [CHAT REQUEST] Il prossimo brano sara' una richiesta della chat: "
                    f"{os.path.basename(music_file)}"
                )
            else:
                if music_file:
                    print(f"⚠️ Richiesta musicale {request.get('id')} pronta ma senza file valido: {music_file}")
                music_file = None

        if not music_file:
            music_file = self.get_random_music(exclude=self.last_music_file)
        if not music_file:
            time.sleep(1)
            return
        if not str(Path(music_file).name).startswith("ai_track_request_"):
            music_file = self._ensure_music_allowed_by_mode(music_file)
        if not music_file:
            time.sleep(1)
            return
            
        self.last_music_file = music_file
        
        metadata = self.build_music_metadata(music_file)
        
        # Gestione Annuncio Vocale in Sidechain
        voice_proc = None
        ducker = None
        if is_requested and request:
            metadata["requested_by"] = request.get("author", "Anonimo")
            metadata["requested_title"] = metadata.get("current_music_title") or request.get("generated_title") or "Brano Richiesto"
            
            announcement_file = TMP_DIR / "request_announcement.wav"
            if _generate_request_announcement(metadata["requested_by"], metadata["requested_title"], announcement_file):
                voice_proc = subprocess.Popen(
                    self._pcm_decode_command(str(announcement_file)),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                ducker = PlayoutSidechainDucker(PCM_SAMPLE_RATE)
        else:
            metadata["requested_by"] = ""
            metadata["requested_title"] = ""

        self.audio_queue.put(
            {
                "type": "metadata",
                "state": metadata,
            }
        )

        print(f"🎵 Brano musicale intermedio (Full Track): {os.path.basename(music_file)}")
        process = subprocess.Popen(
            self._music_decode_command(music_file),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.current_process = process

        try:
            while True:
                if self.is_interrupted():
                    process.terminate()
                    break

                data = process.stdout.read(PCM_CHUNK_BYTES)
                if not data:
                    break
                    
                # Applica mix sidechain con l'annuncio vocale se attivo
                if voice_proc:
                    voice_data = voice_proc.stdout.read(len(data))
                    if voice_data:
                        data = ducker.mix(data, voice_data)
                    else:
                        print("💬 [CHAT SIDECHAIN] Fine lettura annuncio, attesa processo...")
                        self._safe_wait(voice_proc, name="chat_request_voice_proc", timeout=2.0)
                        voice_proc = None
                elif ducker and ducker.current_gain < 0.99:
                    # Dissolvenza di rilascio post-annuncio per ripristinare il volume della musica
                    silence_chunk = b"\x00" * len(data)
                    data = ducker.mix(data, silence_chunk)

                if not self.queue_item({"type": "audio", "data": data}):
                    process.terminate()
                    break
        finally:
            if voice_proc:
                try:
                    voice_proc.terminate()
                    self._safe_wait(voice_proc, name="chat_request_voice_cleanup", timeout=1.0)
                except Exception:
                    pass

        if process.poll() is None:
            process.terminate()
        self._safe_wait(process, name="chat_request_bg_music", timeout=2.0)
        self.current_process = None
