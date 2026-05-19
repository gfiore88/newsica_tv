import os
import sys
import soundfile as sf
from kokoro_onnx import Kokoro

from newsica.audio.tts_text import prepare_text_for_tts
from newsica.domain.characters import get_character

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
SCRIPT_FILE = os.path.join(TMP_DIR, "script.txt")
OUTPUT_AUDIO = os.path.join(TMP_DIR, "audio.wav")

def generate_audio():
    print("Avvio modulo TTS (Kokoro AI locale)...")
    
    character_id = "news"
    if len(sys.argv) > 1:
        character_id = sys.argv[1]
        
    character = get_character(character_id)
    voice = character.voice
    speed = float(os.getenv("TTS_SPEED", character.speed))
    print(f"Uso il personaggio: {character.id} (Voce: {voice}, velocità: {speed})")
    
    if not os.path.exists(SCRIPT_FILE):
        print(f"Errore: File {SCRIPT_FILE} non trovato. Esegui prima llm_processor.py.")
        sys.exit(1)
        
    with open(SCRIPT_FILE, 'r', encoding='utf-8') as f:
        raw_text = f.read().strip()
        
    if not raw_text:
        print("Errore: Il copione è vuoto.")
        sys.exit(1)
        
    multipart_file = os.path.join(TMP_DIR, "is_multipart.txt")
    
    print("Inizializzazione di Kokoro ONNX...")
    try:
        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        
        if "[MUSIC_BREAK]" in raw_text:
            parts = [p.strip() for p in raw_text.split("[MUSIC_BREAK]") if p.strip()]
            num_parts = len(parts)
            print(f"Rilevato copione multi-part! Generazione di {num_parts} parti separate...")
            
            # Pulisci vecchi file audio di parti precedenti per evitare sovrapposizioni
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
                
            # Scrive il numero totale di parti nel semaforo
            with open(multipart_file, "w") as sf_file:
                sf_file.write(str(num_parts))
            print(f"✅ Generati con successo {num_parts} file audio per lo show multi-part!")
        else:
            print("Copione standard a parte singola.")
            text = prepare_text_for_tts(raw_text)
            samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang="it")
            sf.write(OUTPUT_AUDIO, samples, sample_rate)
            
            # Rimuove semaforo se esistente
            if os.path.exists(multipart_file):
                os.remove(multipart_file)
            print("✅ File audio generato con successo tramite Kokoro AI!")
            
    except Exception as e:
        print(f"❌ Errore durante la generazione dell'audio con Kokoro: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_audio()
