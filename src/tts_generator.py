import os
import sys
import re
import soundfile as sf
import numpy as np
from kokoro_onnx import Kokoro

from newsica.audio.tts_text import prepare_text_for_tts
from newsica.domain.characters import get_character

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
SCRIPT_FILE = os.path.join(TMP_DIR, "script.txt")
OUTPUT_AUDIO = os.path.join(TMP_DIR, "audio.wav")

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

def generate_audio():
    print("Avvio modulo TTS...")
    
    character_id = "news"
    if len(sys.argv) > 1:
        character_id = sys.argv[1]
        
    character = get_character(character_id)
    voice = character.voice
    speed = float(os.getenv("TTS_SPEED", character.speed))
    
    if not os.path.exists(SCRIPT_FILE):
        print(f"Errore: File {SCRIPT_FILE} non trovato. Esegui prima llm_processor.py.")
        sys.exit(1)
        
    with open(SCRIPT_FILE, 'r', encoding='utf-8') as f:
        raw_text = f.read().strip()
        
    if not raw_text:
        print("Errore: Il copione è vuoto.")
        sys.exit(1)
        
    multipart_file = os.path.join(TMP_DIR, "is_multipart.txt")
    
    # Rilevamento automatico dell'uso di Qwen3-TTS (per rubriche podcast)
    use_qwen = (voice == "qwen3" or character_id == "podcast")
    
    if use_qwen:
        print(f"🎙️ Rilevato personaggio Podcast. Utilizzo Qwen3-TTS locale per {character.display_name}...")
        try:
            # Import lazy del generatore per evitare overhead di PyTorch/torch sulle altre rubriche
            from newsica.audio.qwen_tts import generate_voice_design_segment
            
            # Parsing dei tag speaker [SPEAKER: Nome]
            pattern = re.compile(r'\[SPEAKER:\s*([^\]]+)\]')
            matches = list(pattern.finditer(raw_text))
            segments = []
            
            if not matches:
                # Fallback se non ci sono tag: tutto a Chiara
                print("⚠️ Attenzione: Nessun tag SPEAKER rilevato. Uso Chiara come conduttore di default.")
                segments.append(("Chiara", raw_text))
            else:
                for idx, match in enumerate(matches):
                    speaker = match.group(1).strip()
                    start_idx = match.end()
                    end_idx = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_text)
                    text_content = raw_text[start_idx:end_idx].strip()
                    if text_content:
                        segments.append((speaker, text_content))
            
            print(f"Trovati {len(segments)} segmenti di dialogo. Inizio sintesi alternata...")
            
            combined_samples = []
            sample_rate = 24000
            
            # Pulisci file temporanei di segmenti precedenti
            for f_name in os.listdir(TMP_DIR):
                if f_name.startswith("podcast_seg_") and f_name.endswith(".wav"):
                    try:
                        os.remove(os.path.join(TMP_DIR, f_name))
                    except Exception:
                        pass
            
            for idx, (speaker, text) in enumerate(segments):
                seg_num = idx + 1
                seg_file = os.path.join(TMP_DIR, f"podcast_seg_{seg_num}.wav")
                
                # Associa la descrizione vocale (Voice Design) in base allo speaker caricandola dinamicamente
                instruct = get_qwen_speaker_instruction(speaker)
                
                print(f"🎙️ Sintesi Turno {seg_num}/{len(segments)} | Speaker: {speaker}")
                clean_text = prepare_text_for_tts(text, keep_brackets=True)
                
                success = generate_voice_design_segment(clean_text, instruct, seg_file)
                if success and os.path.exists(seg_file):
                    data, sr = sf.read(seg_file, dtype='float32')
                    sample_rate = sr
                    combined_samples.append((data, speaker))
                else:
                    print(f"❌ Errore nella generazione del segmento {seg_num} per {speaker}.")
            
            # Unione dei segmenti audio con micro-pause fisiologiche tra un interlocutore e l'altro
            if combined_samples:
                print("🎛️ Unione dei segmenti audio in corso...")
                final_samples_list = []
                
                # 0.3 secondi di silenzio a 24000Hz per distanziare i turni
                silence_len = int(sample_rate * 0.3)
                silence_samples = np.zeros(silence_len, dtype=np.float32)
                
                for idx, (data, speaker) in enumerate(combined_samples):
                    if idx > 0:
                        # Inietta silenzio tra i turni di parola
                        final_samples_list.append(silence_samples)
                    final_samples_list.append(data)
                
                final_samples = np.concatenate(final_samples_list, axis=0)
                sf.write(OUTPUT_AUDIO, final_samples, sample_rate)
                
                # Rimuove semaforo multipart se esistente (i podcast sono file unici)
                if os.path.exists(multipart_file):
                    os.remove(multipart_file)
                    
                print(f"✅ Podcast '{character.display_name}' sintetizzato con successo in: {OUTPUT_AUDIO}")
            else:
                print("❌ Errore critico: Nessun segmento audio generato.")
                sys.exit(1)
                
        except Exception as e:
            print(f"❌ Errore critico durante la generazione del podcast con Qwen3-TTS: {e}")
            sys.exit(1)
            
    else:
        # Percorso Kokoro standard
        print(f"Uso il personaggio: {character.id} (Voce: {voice}, velocità: {speed})")
        print(f"Inizializzazione di Kokoro ONNX per {character.display_name}...")
        try:
            kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
            
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
                    samples, sample_rate = kokoro.create(part_text, voice=voice, speed=speed, lang="it")
                    sf.write(os.path.join(TMP_DIR, f"audio_part{part_num}.wav"), samples, sample_rate)
                    
                with open(multipart_file, "w") as sf_file:
                    sf_file.write(str(num_parts))
                print(f"✅ Generati con successo {num_parts} file audio per lo show multi-part!")
            else:
                print("Copione standard a parte singola.")
                text = prepare_text_for_tts(raw_text)
                samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang="it")
                sf.write(OUTPUT_AUDIO, samples, sample_rate)
                
                if os.path.exists(multipart_file):
                    os.remove(multipart_file)
                print("✅ File audio generato con successo tramite Kokoro AI!")
                
        except Exception as e:
            print(f"❌ Errore durante la generazione dell'audio con Kokoro: {e}")
            sys.exit(1)

if __name__ == "__main__":
    generate_audio()
