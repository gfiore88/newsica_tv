import datetime
import os
import queue
import subprocess
import time

from newsica.audio.music_library import MusicLibrary
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
            "-filter:a", "volume=0.8",
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
            "[0:a]volume=1.5,asplit=2[v_main][v_side]; "
            "[1:a]volume=0.25[m]; "
            "[m][v_side]sidechaincompress=threshold=0.03:ratio=20:attack=50:release=1000[music]; "
            "[v_main][music]amix=inputs=2:duration=first:dropout_transition=0",
            "-f", "s16le",
            "-ar", str(PCM_SAMPLE_RATE),
            "-ac", str(PCM_CHANNELS),
            "pipe:1",
        ]

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
        print(f"Mixaggio in corso: Voce + {os.path.basename(music_file)}")

        if block_info:
            self.audio_queue.put({"type": "metadata", "state": block_info})

        process = subprocess.Popen(self._mix_command(music_file, voice_file), stdout=subprocess.PIPE)
        self.current_process = process

        print("Caricamento audio nella coda...")
        count = 0
        while True:
            if self.is_interrupted():
                print("⏭️ Interrompo il mixaggio regolare.")
                process.terminate()
                break

            data = process.stdout.read(PCM_CHUNK_BYTES)
            if not data:
                break
            if not self.queue_item({"type": "audio", "data": data}):
                process.terminate()
                break
            count += 1

        process.wait()
        self.current_process = None
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
        self.last_music_file = music_file

        print(f"🎵 Brano musicale di riempimento: {os.path.basename(music_file)}")
        process = subprocess.Popen(self._music_decode_command(music_file), stdout=subprocess.PIPE)
        self.current_process = process

        while datetime.datetime.now() < deadline:
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

    def queue_single_music_track(self):
        if self.is_interrupted():
            return

        music_file = self.get_random_music(exclude=self.last_music_file)
        if not music_file:
            time.sleep(1)
            return
        self.last_music_file = music_file

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

