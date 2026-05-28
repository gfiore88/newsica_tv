import os
import sys
import numpy as np
from kokoro_onnx import Kokoro

# Aggiungi src al path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from newsica.utils.voice_helper import get_voice_style_for_character

def main():
    print("🎬 Inizializzazione di Kokoro ONNX per test...")
    onnx_path = "kokoro-v1.0.onnx"
    voices_path = "voices-v1.0.bin"
    
    if not os.path.exists(onnx_path) or not os.path.exists(voices_path):
        print("❌ Modelli Kokoro non trovati nella root.")
        sys.exit(1)
        
    kokoro = Kokoro(onnx_path, voices_path)
    
    characters_to_test = ["chiara", "maya", "leo", "giorgio", "colonnello", "unknown"]
    
    print("\n🔍 Test recupero vettori di voce:")
    for char in characters_to_test:
        print(f"\n👉 Personaggio: {char.upper()}")
        style = get_voice_style_for_character(kokoro, char)
        
        if isinstance(style, str):
            print(f"✅ Ritornata stringa di base: '{style}'")
        elif isinstance(style, np.ndarray):
            print(f"✅ Ritornata perturbazione personalizzata (array NumPy)")
            print(f"📊 Shape: {style.shape} | Precisione: {style.dtype}")
            # Verifica che sia float32
            assert style.dtype == np.float32, "Il tipo del vettore deve essere float32!"
            # Verifica che non ci siano NaN/Inf
            assert not np.isnan(style).any(), "Il vettore contiene valori NaN!"
            assert not np.isinf(style).any(), "Il vettore contiene valori Inf!"
            print("✨ Vettore super super valido!")
        else:
            print(f"❌ Tipo ritornato sconosciuto: {type(style)}")
            sys.exit(1)

    print("\n🎉 Tutti i test del Voice Helper sono passati con successo!")

if __name__ == "__main__":
    main()
