import os
import sys
import re
import json
import subprocess
import soundfile as sf
import numpy as np
from newsica.utils.voice_helper import get_cached_kokoro

from newsica.audio.tts_text import prepare_text_for_tts
from newsica.domain.characters import get_character

TMP_DIR = os.getenv("NEWSICA_TMP_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp"))
SCRIPT_FILE = os.path.join(TMP_DIR, "script.txt")
OUTPUT_AUDIO = os.path.join(TMP_DIR, "audio.wav")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CHATTERBOX_PYTHON = os.getenv(
    "CHATTERBOX_PYTHON",
    os.path.join(BASE_DIR, ".venv_tts_spike", "bin", "python"),
)
CHATTERBOX_SCRIPT = os.path.join(BASE_DIR, "src", "newsica", "audio", "chatterbox_tts.py")
VOICE_REFS_DIR = os.path.join(BASE_DIR, "assets", "voice_refs")
CHATTERBOX_REFS = {
    "giulia": os.path.join(VOICE_REFS_DIR, "giulia_reference.wav"),
    "marco": os.path.join(VOICE_REFS_DIR, "marco_reference.wav"),
}
KOKORO_PODCAST_VOICES = {
    "giulia": "if_sara",
    "marco": "im_nicola",
}
PODCAST_TARGET_RMS_DBFS = float(os.getenv("PODCAST_TARGET_RMS_DBFS", "-20.0"))
PODCAST_MAX_PEAK_DBFS = float(os.getenv("PODCAST_MAX_PEAK_DBFS", "-1.5"))

VOICES_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "newsica", "editorial", "prompts", "voices")

def get_qwen_speaker_instruction(speaker_name):
    # Rimuove caratteri speciali e converte in minuscolo
    speaker_clean = re.sub(r'[^a-zA-Z0-9]', '', speaker_name).lower()
    voice_file = os.path.join(VOICES_PROMPTS_DIR, f"{speaker_clean}.txt")
    
    # 1. Prova a caricare il file specifico (es. chiara.txt o leo.txt)
    if os.path.exists(voice_file):
        try:
            with open(voice_file, "r", encoding="utf-8") as vf:
                return vf.read().strip()
        except Exception as e:
            print(f"⚠️ Impossibile leggere il file vocale per {speaker_name}: {e}")
            
    # 2. Fallback su default.txt
    default_file = os.path.join(VOICES_PROMPTS_DIR, "default.txt")
    if os.path.exists(default_file):
        try:
            with open(default_file, "r", encoding="utf-8") as vf:
                return vf.read().strip()
        except Exception:
            pass
            
    # 3. Fallback finale hardcoded protettivo se non ci sono file su disco
    if speaker_clean == "giulia":
        return "A mature, highly professional adult Italian female news anchor, speaking standard Italian with a flawless broadcast accent and perfect natural cadence."
    elif speaker_clean == "marco":
        return "A mature, warm, and highly professional adult Italian male radio host, speaking standard Italian with an engaging, natural conversational cadence."
    
    return "A mature and professional native Italian speaker with a clear voice."

def get_speaker_key(speaker_name):
    return re.sub(r'[^a-zA-Z0-9]', '', speaker_name).lower()

def parse_speaker_segments(raw_text):
    pattern = re.compile(r'\[SPEAKER:\s*([^\]]+)\]')
    matches = list(pattern.finditer(raw_text))
    segments = []

    if not matches:
        print("⚠️ Attenzione: Nessun tag SPEAKER rilevato. Uso Giulia come conduttrice di default.")
        return [("Giulia", raw_text)]

    for idx, match in enumerate(matches):
        speaker = match.group(1).strip()
        start_idx = match.end()
        end_idx = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_text)
        text_content = raw_text[start_idx:end_idx].strip()
        if text_content:
            segments.append((speaker, text_content))

    return segments

def cleanup_podcast_segments():
    for f_name in os.listdir(TMP_DIR):
        if f_name.startswith("podcast_seg_") and f_name.endswith(".wav"):
            try:
                os.remove(os.path.join(TMP_DIR, f_name))
            except Exception:
                pass

def _speaker_gain_db_env(speaker):
    speaker_key = get_speaker_key(speaker)
    return float(os.getenv(f"PODCAST_SPEAKER_GAIN_{speaker_key.upper()}_DB", "0.0"))

def _normalize_segment_level(data, speaker):
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak <= 1e-6:
        return data

    gate = max(peak * 0.08, 1e-4)
    active = data[np.abs(data) >= gate]
    if active.size == 0:
        active = data[np.abs(data) >= 1e-5]
    if active.size == 0:
        active = data

    rms = float(np.sqrt(np.mean(np.square(active), dtype=np.float64)))
    if rms <= 1e-9:
        return data

    current_rms_db = 20.0 * np.log10(rms)
    gain_db = PODCAST_TARGET_RMS_DBFS - current_rms_db
    gain_db += _speaker_gain_db_env(speaker)

    target_peak_linear = 10.0 ** (PODCAST_MAX_PEAK_DBFS / 20.0)
    max_gain_db = 20.0 * np.log10(target_peak_linear / peak)
    applied_gain_db = min(gain_db, max_gain_db)
    gain = 10.0 ** (applied_gain_db / 20.0)
    normalized = data * gain
    return np.clip(normalized, -1.0, 1.0)

def write_combined_podcast(segment_files, output_path):
    combined_samples = []
    sample_rate = 24000

    for seg_file, speaker in segment_files:
        data, sr = sf.read(seg_file, dtype='float32')
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        if combined_samples and sr != sample_rate:
            raise RuntimeError(f"Sample rate diverso nel segmento {seg_file}: {sr} != {sample_rate}")
        sample_rate = sr
        data = _normalize_segment_level(data, speaker)
        combined_samples.append((data, speaker))

    if not combined_samples:
        return False

    print("🎛️ Unione dei segmenti audio in corso...")
    final_samples_list = []
    silence_len = int(sample_rate * 0.3)
    silence_samples = np.zeros(silence_len, dtype=np.float32)

    for idx, (data, speaker) in enumerate(combined_samples):
        if idx > 0:
            final_samples_list.append(silence_samples)
        final_samples_list.append(data)

    final_samples = np.concatenate(final_samples_list, axis=0)
    sf.write(output_path, final_samples, sample_rate)
    return True

def generate_podcast_with_chatterbox(segments):
    if not os.path.exists(CHATTERBOX_PYTHON):
        raise RuntimeError(f"Ambiente Chatterbox non trovato: {CHATTERBOX_PYTHON}")
    if not os.path.exists(CHATTERBOX_SCRIPT):
        raise RuntimeError(f"Script Chatterbox non trovato: {CHATTERBOX_SCRIPT}")

    segment_payload = []
    for speaker, text in segments:
        speaker_key = get_speaker_key(speaker)
        reference_audio = CHATTERBOX_REFS.get(speaker_key)
        if reference_audio is None or not os.path.exists(reference_audio):
            raise RuntimeError(f"Reference Chatterbox mancante per speaker '{speaker}'")
        segment_payload.append({
            "speaker": speaker,
            "text": prepare_text_for_tts(text),
            "reference_audio": reference_audio,
        })

    segments_json = os.path.join(TMP_DIR, "chatterbox_segments.json")
    manifest_json = os.path.join(TMP_DIR, "chatterbox_manifest.json")
    output_dir = os.path.join(TMP_DIR, "chatterbox_podcast")
    os.makedirs(output_dir, exist_ok=True)

    with open(segments_json, "w", encoding="utf-8") as f:
        json.dump(segment_payload, f, ensure_ascii=False, indent=2)

    print("🎙️ Sintesi podcast con Chatterbox Multilingual...")
    subprocess.run(
        [
            CHATTERBOX_PYTHON,
            CHATTERBOX_SCRIPT,
            "--segments-json", segments_json,
            "--output-dir", output_dir,
            "--manifest-json", manifest_json,
        ],
        cwd=BASE_DIR,
        check=True,
    )

    with open(manifest_json, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    segment_files = [(item["path"], item["speaker"]) for item in manifest]
    return write_combined_podcast(segment_files, OUTPUT_AUDIO)

def generate_podcast_with_kokoro_fallback(segments):
    print("⚠️ Fallback podcast: uso Kokoro con voci Giulia/Marco.")
    kokoro = get_cached_kokoro()
    segment_files = []

    for idx, (speaker, text) in enumerate(segments):
        speaker_key = get_speaker_key(speaker)
        voice = KOKORO_PODCAST_VOICES.get(speaker_key, "if_sara")
        seg_file = os.path.join(TMP_DIR, f"podcast_seg_{idx + 1}.wav")
        clean_text = prepare_text_for_tts(text)
        print(f"🎙️ Kokoro fallback turno {idx + 1}/{len(segments)} | Speaker: {speaker} | Voce: {voice}")
        samples, sample_rate = kokoro.create(clean_text, voice=voice, speed=1.0, lang="it")
        sf.write(seg_file, samples, sample_rate)
        segment_files.append((seg_file, speaker))

    return write_combined_podcast(segment_files, OUTPUT_AUDIO)

def generate_audio(character_id=None):
    print("Avvio modulo TTS...")
    
    if character_id is None:
        character_id = "news"
        if len(sys.argv) > 1:
            character_id = sys.argv[1]
        
    character = get_character(character_id)
    voice = character.voice
    speed = float(os.getenv("TTS_SPEED", character.speed))
    
    if not os.path.exists(SCRIPT_FILE):
        raise RuntimeError(f"Errore: File {SCRIPT_FILE} non trovato. L'agente di integrazione (AIIntegratorAgent) non ha prodotto il copione in tempo.")
        
    with open(SCRIPT_FILE, 'r', encoding='utf-8') as f:
        raw_text = f.read().strip()
        
    if not raw_text:
        raise RuntimeError("Errore: Il copione è vuoto.")
        
    multipart_file = os.path.join(TMP_DIR, "is_multipart.txt")
    
    # Rilevamento automatico del provider podcast a due voci.
    # Il valore "qwen3" resta compatibile nel registry, ma il provider primario e' Chatterbox.
    use_podcast_tts = (voice in ("qwen3", "chatterbox") or character_id == "podcast")
    
    if use_podcast_tts:
        print(f"🎙️ Rilevato personaggio Podcast. Utilizzo Chatterbox Multilingual per {character.display_name}...")
        try:
            segments = parse_speaker_segments(raw_text)
            print(f"Trovati {len(segments)} segmenti di dialogo. Inizio sintesi alternata...")

            cleanup_podcast_segments()

            try:
                success = generate_podcast_with_chatterbox(segments)
            except Exception as chatterbox_error:
                print(f"⚠️ Chatterbox non disponibile o fallito: {chatterbox_error}")
                cleanup_podcast_segments()
                success = generate_podcast_with_kokoro_fallback(segments)

            if not success:
                raise RuntimeError("Errore critico: Nessun segmento audio generato.")

            # Rimuove semaforo multipart se esistente (i podcast sono file unici)
            if os.path.exists(multipart_file):
                os.remove(multipart_file)

            print(f"✅ Podcast '{character.display_name}' sintetizzato con successo in: {OUTPUT_AUDIO}")
                
        except Exception as e:
            raise RuntimeError(f"Errore critico durante la generazione del podcast: {e}")
            
    else:
        print(f"Uso il personaggio: {character.id} (Voce: {voice}, velocità: {speed})")
        print(f"Inizializzazione di Kokoro ONNX per {character.display_name}...")
        try:
            kokoro = get_cached_kokoro()
            
            # Carica lo stile vocale personalizzato (vettore perturbato o stringa base)
            from newsica.utils.voice_helper import get_voice_style_for_character
            voice_style = get_voice_style_for_character(kokoro, character.id)
            
            if "[MUSIC_BREAK]" in raw_text:
                parts = [p.strip() for p in raw_text.split("[MUSIC_BREAK]") if p.strip()]
                num_parts = len(parts)
                print(f"Rilevato copione multi-part! Generazione di {num_parts} parti separate...")
                
                # Pulisci vecchi file audio
                for f_name in os.listdir(TMP_DIR):
                    if f_name.startswith("audio_part") and f_name.endswith(".wav"):
                        try:
                            os.remove(os.path.join(TMP_DIR, f_name))
                        except Exception:
                            pass
    
                for idx, part in enumerate(parts):
                    part_text = prepare_text_for_tts(part)
                    part_num = idx + 1
                    print(f"Generazione Parte {part_num} di {num_parts}...")
                    samples, sample_rate = kokoro.create(part_text, voice=voice_style, speed=speed, lang="it")
                    sf.write(os.path.join(TMP_DIR, f"audio_part{part_num}.wav"), samples, sample_rate)
                    
                with open(multipart_file, "w") as sf_file:
                    sf_file.write(str(num_parts))
                print(f"✅ Generati con successo {num_parts} file audio per lo show multi-part!")
            else:
                print("Copione standard a parte singola.")
                text = prepare_text_for_tts(raw_text)
                samples, sample_rate = kokoro.create(text, voice=voice_style, speed=speed, lang="it")
                sf.write(OUTPUT_AUDIO, samples, sample_rate)
                
                if os.path.exists(multipart_file):
                    os.remove(multipart_file)
                print("✅ File audio generato con successo tramite Kokoro AI!")
                
        except Exception as e:
            raise RuntimeError(f"Errore durante la generazione dell'audio con Kokoro: {e}")

if __name__ == "__main__":
    generate_audio()
