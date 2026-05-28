import os
import sys
import subprocess
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "samples")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configurazione della miscelazione (Blending) per ogni personaggio
CHARACTERS_SAMPLES = {
    "chiara": {
        "text": "Ciao, sono Chiara, la conduttrice ufficiale delle news di NewsicaTV. La mia voce è chiara, diretta e professionale.",
        "blend": [("if_sara", 1.0)],
        "speed": 1.05
    },
    "maya": {
        "text": "Un saluto da Maya! Benvenuti nella nostra rubrica quotidiana dedicata al benessere, alla salute e al lifestyle su NewsicaTV.",
        "blend": [("if_sara", 0.65), ("af_sky", 0.35)],  # Sara + Sky (dolce e melodiosa)
        "speed": 0.90
    },
    "leo": {
        "text": "Grande sport in primo piano! Sono Leo e oggi entriamo nel vivo dei campionati e delle sfide più accese su NewsicaTV.",
        "blend": [("im_nicola", 0.60), ("am_adam", 0.40)],  # Nicola + Adam (atletico, energico)
        "speed": 1.05
    },
    "giorgio": {
        "text": "Motori accesi e adrenalina a mille! Sono Giorgio e vi porto a scoprire i segreti delle supercar e delle moto più veloci del pianeta.",
        "blend": [("im_nicola", 0.70), ("am_onyx", 0.30)],  # Nicola + Onyx (ricco, profondo, carismatico)
        "speed": 1.00
    },
    "colonnello": {
        "text": "Buongiorno dal Colonnello. Vediamo subito l'evoluzione delle perturbazioni e le previsioni meteo dettagliate per le prossime ore.",
        "blend": [("im_nicola", 0.55), ("am_michael", 0.45)],  # Nicola + Michael (chiaro, pacato e istituzionale)
        "speed": 0.95
    }
}

def generate_voice_vector(kokoro, blend_config):
    style = None
    for voice_name, weight in blend_config:
        v_style = kokoro.get_voice_style(voice_name)
        if style is None:
            style = v_style * weight
        else:
            style += v_style * weight
    return style.astype(np.float32)

def main():
    print("🎬 Inizializzazione modello Kokoro...")
    kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
    
    ffmpeg_cmd = "ffmpeg"
    if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"):
        ffmpeg_cmd = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
        
    for name, config in CHARACTERS_SAMPLES.items():
        print(f"\n🎙️ Generazione provino per: {name.upper()}")
        
        # Genera il vettore di voce miscelato
        custom_voice = generate_voice_vector(kokoro, config["blend"])
        
        # Sintetizza l'audio
        samples, sample_rate = kokoro.create(
            config["text"], 
            voice=custom_voice, 
            speed=config["speed"], 
            lang="it"
        )
        
        wav_path = os.path.join(TMP_DIR, f"sample_{name}.wav")
        mp3_path = os.path.join(OUTPUT_DIR, f"sample_{name}.mp3")
        
        # Scrivi il file WAV temporaneo
        sf.write(wav_path, samples, sample_rate)
        
        # Converti in MP3 tramite FFmpeg
        print(f"📦 Conversione in MP3: {os.path.basename(mp3_path)}")
        cmd = [
            ffmpeg_cmd, "-y",
            "-i", wav_path,
            "-codec:a", "libmp3lame",
            "-qscale:a", "2",
            mp3_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Pulisci WAV temporaneo
        if os.path.exists(wav_path):
            os.remove(wav_path)
            
        print(f"✅ Provino completato: file://{mp3_path}")

    print("\n🎉 Generazione completata con successo! Trovi i file MP3 nella cartella 'output/samples/'.")

if __name__ == "__main__":
    main()
