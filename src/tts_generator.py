import os
import sys
import soundfile as sf
from kokoro_onnx import Kokoro

TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
SCRIPT_FILE = os.path.join(TMP_DIR, "script.txt")
OUTPUT_AUDIO = os.path.join(TMP_DIR, "audio.wav")

VOICES = {
    "news": "if_sara",
    "sport": "im_nicola",
    "meteo": "im_nicola"
}

def generate_audio():
    print("Avvio modulo TTS (Kokoro AI locale)...")
    
    character = "news"
    if len(sys.argv) > 1:
        character = sys.argv[1]
        
    voice = VOICES.get(character, "if_sara")
    print(f"Uso il personaggio: {character} (Voce: {voice})")
    
    if not os.path.exists(SCRIPT_FILE):
        print(f"Errore: File {SCRIPT_FILE} non trovato. Esegui prima llm_processor.py.")
        sys.exit(1)
        
    with open(SCRIPT_FILE, 'r', encoding='utf-8') as f:
        text = f.read().strip()
        
    if not text:
        print("Errore: Il copione è vuoto.")
        sys.exit(1)
        
    print("Inizializzazione di Kokoro ONNX...")
    try:
        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0, lang="it")
        sf.write(OUTPUT_AUDIO, samples, sample_rate)
        print("✅ File audio generato con successo tramite Kokoro AI!")
    except Exception as e:
        print(f"❌ Errore durante la generazione dell'audio con Kokoro: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_audio()

