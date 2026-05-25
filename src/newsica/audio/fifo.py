import os
import time
import subprocess
import queue
import numpy as np

from newsica.audio.settings import PCM_CHANNELS, PCM_CHUNK_BYTES, PCM_SAMPLE_RATE, resolve_ffmpeg_cmd
from newsica.broadcast.runtime_state import get_current_state, write_state_files

FFMPEG_CMD = resolve_ffmpeg_cmd()

def apply_display_metadata(metadata_item):
    _DISPLAY_FIELDS = {
        "current_block", "current_title", "next_block",
        "next_start", "breaking_news_available", "last_update",
        "current_music_title", "requested_by", "requested_title",
    }
    existing_state = get_current_state()
    for field in _DISPLAY_FIELDS:
        if field in metadata_item["state"]:
            existing_state[field] = metadata_item["state"][field]
    write_state_files(existing_state)

def is_music_safe_for_chime(state):
    if not state or state.get("status") != "ON_AIR":
        return False
    return (
        state.get("current_block") == "music_only"
        or state.get("current_segment") == "music_rotation_until_deadline"
    )

class FifoWriter:
    def __init__(self, fifo_fd, audio_queue):
        self.fifo_fd = fifo_fd
        self.audio_queue = audio_queue
        
    def write_chunk(self, data, blocking=True):
        view = memoryview(data)
        written_total = 0
        while written_total < len(view):
            try:
                if self.fifo_fd is None:
                    raise BrokenPipeError
                written = os.write(self.fifo_fd, view[written_total:])
                if written == 0:
                    raise BrokenPipeError
                written_total += written
            except BlockingIOError:
                if not blocking:
                    return False
                time.sleep(0.02)
        return True

    def apply_preventive_fade_out_and_write(self):
        chunks = []
        while len(chunks) < 10:
            try:
                item = self.audio_queue.get_nowait()
                if isinstance(item, dict) and item.get("type") == "metadata":
                    self.audio_queue.task_done()
                    continue
                data = item["data"] if isinstance(item, dict) else item
                chunks.append(data)
                self.audio_queue.task_done()
            except queue.Empty:
                break
                
        if not chunks:
            return
            
        num_chunks = len(chunks)
        for idx in range(num_chunks):
            data = chunks[idx]
            samples = np.frombuffer(data, dtype=np.int16).copy()
            start_factor = (num_chunks - idx) / num_chunks
            end_factor = (num_chunks - idx - 1) / num_chunks
            factors = np.linspace(start_factor, end_factor, len(samples))
            faded_data = (samples * factors).astype(np.int16).tobytes()
            try:
                self.write_chunk(faded_data)
            except BrokenPipeError:
                raise

    def get_next_audio_chunk_for_overlay(self, silence):
        while True:
            try:
                item = self.audio_queue.get_nowait()
            except queue.Empty:
                return silence

            try:
                if isinstance(item, dict) and item.get("type") == "metadata":
                    apply_display_metadata(item)
                    continue

                return item["data"] if isinstance(item, dict) else item
            finally:
                self.audio_queue.task_done()

    def overlay_chime_on_music(self, chime_file, silence):
        cmd_ffmpeg = [
            FFMPEG_CMD,
            "-hide_banner",
            "-loglevel", "error",
            "-i", chime_file,
            "-f", "s16le",
            "-ar", str(PCM_SAMPLE_RATE),
            "-ac", str(PCM_CHANNELS),
            "pipe:1"
        ]
        proc = subprocess.Popen(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        # Parametri Sidechain / Ducking
        threshold = 0.02
        ratio = 20.0
        chunk_dur = 2048.0 / 24000.0  # Durata di un chunk (~85.3ms)
        
        # Coefficienti per Attack (~50ms) e Release (~800ms)
        attack_coef = 1.0 - np.exp(-chunk_dur / 0.05)   # ~0.82
        release_coef = 1.0 - np.exp(-chunk_dur / 0.8)    # ~0.10
        
        envelope = 0.0
        current_gain = 0.78  # Volume base normale della musica
        normal_gain = 0.78
        min_gain = 0.15      # Volume minimo a cui viene abbassata la musica
        overlay_volume = 1.3 # Boost per rendere la voce del segnale orario nitida e chiara
        
        chunks = 0
        try:
            while True:
                chime_chunk = proc.stdout.read(PCM_CHUNK_BYTES)
                if not chime_chunk:
                    break
                    
                music_chunk = self.get_next_audio_chunk_for_overlay(silence[:len(chime_chunk)])
                min_len = min(len(music_chunk), len(chime_chunk))
                
                if min_len > 0:
                    base = np.frombuffer(music_chunk[:min_len], dtype=np.int16).astype(np.float32)
                    overlay = np.frombuffer(chime_chunk[:min_len], dtype=np.int16).astype(np.float32)
                    
                    # Calcola il picco della voce normalizzato in [0, 1]
                    voice_peak = np.max(np.abs(overlay)) / 32768.0
                    
                    # Aggiorna l'inviluppo con l'inseguitore
                    if voice_peak > envelope:
                        envelope += attack_coef * (voice_peak - envelope)
                    else:
                        envelope += release_coef * (voice_peak - envelope)
                        
                    # Calcola il gain di sidechain basato sull'inviluppo
                    if envelope > threshold:
                        env_clamped = max(envelope, 1e-5)
                        input_db = 20.0 * np.log10(env_clamped)
                        thresh_db = 20.0 * np.log10(threshold)
                        over_db = input_db - thresh_db
                        attenuation_db = over_db * (1.0 - 1.0 / ratio)
                        target_gain_factor = 10.0 ** (-attenuation_db / 20.0)
                        target_gain = min_gain + (normal_gain - min_gain) * target_gain_factor
                        target_gain = min(target_gain, normal_gain)
                    else:
                        target_gain = normal_gain
                        
                    # Rampa lineare di gain all'interno del chunk per evitare pop/click
                    gains = np.linspace(current_gain, target_gain, len(base), dtype=np.float32)
                    current_gain = target_gain
                    
                    # Mix dei segnali
                    mixed = (base * gains) + (overlay * overlay_volume)
                    mixed_bytes = np.clip(mixed, -32768, 32767).astype(np.int16).tobytes()
                    
                    self.write_chunk(mixed_bytes)
                else:
                    self.write_chunk(music_chunk)
                    
                chunks += 1
                
            # --- Fase di rilascio post-chime ---
            while current_gain < (normal_gain - 0.01):
                music_chunk = self.get_next_audio_chunk_for_overlay(silence)
                base = np.frombuffer(music_chunk, dtype=np.int16).astype(np.float32)
                
                # La voce è ora totalmente silenziosa
                voice_peak = 0.0
                envelope += release_coef * (voice_peak - envelope)
                
                if envelope > threshold:
                    env_clamped = max(envelope, 1e-5)
                    input_db = 20.0 * np.log10(env_clamped)
                    thresh_db = 20.0 * np.log10(threshold)
                    over_db = input_db - thresh_db
                    attenuation_db = over_db * (1.0 - 1.0 / ratio)
                    target_gain_factor = 10.0 ** (-attenuation_db / 20.0)
                    target_gain = min_gain + (normal_gain - min_gain) * target_gain_factor
                    target_gain = min(target_gain, normal_gain)
                else:
                    target_gain = normal_gain
                    
                gains = np.linspace(current_gain, target_gain, len(base), dtype=np.float32)
                current_gain = target_gain
                
                mixed = base * gains
                mixed_bytes = np.clip(mixed, -32768, 32767).astype(np.int16).tobytes()
                self.write_chunk(mixed_bytes)
                chunks += 1
                
        finally:
            proc.wait()
        print(f"🔔 Segnale orario mixato sopra la musica ({chunks} chunks con sidechain).")

def mix_pcm_chunks(base_data, overlay_data, base_volume=0.78, overlay_volume=1.0):
    if len(base_data) < len(overlay_data):
        base_data = base_data + (b"\x00" * (len(overlay_data) - len(base_data)))
    elif len(base_data) > len(overlay_data):
        base_data = base_data[:len(overlay_data)]

    base = np.frombuffer(base_data, dtype=np.int16).astype(np.float32)
    overlay = np.frombuffer(overlay_data, dtype=np.int16).astype(np.float32)
    mixed = (base * base_volume) + (overlay * overlay_volume)
    return np.clip(mixed, -32768, 32767).astype(np.int16).tobytes()
