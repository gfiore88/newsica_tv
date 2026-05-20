from __future__ import annotations

import os
import torch
import soundfile as sf
import numpy as np

# Cache per il caricamento lazy del modello Qwen3-TTS
_qwen_model = None
_model_device = None

def get_qwen_device() -> str:
    """Rileva automaticamente il device migliore (MPS per macOS, CUDA per Nvidia, CPU come fallback)."""
    global _model_device
    if _model_device is not None:
        return _model_device

    if torch.backends.mps.is_available():
        _model_device = "mps"
        print("🚀 Qwen3-TTS: Rilevata accelerazione hardware Apple Silicon (MPS).")
    elif torch.cuda.is_available():
        _model_device = "cuda"
        print("🚀 Qwen3-TTS: Rilevata accelerazione hardware NVIDIA (CUDA).")
    else:
        _model_device = "cpu"
        print("⚠️ Qwen3-TTS: Nessuna accelerazione hardware rilevata. Uso CPU (lento).")
    return _model_device

def load_qwen_model(model_name: str = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"):
    """Carica lazy il modello Qwen3-TTS in memoria spostandolo sul device corretto."""
    global _qwen_model
    if _qwen_model is not None:
        return _qwen_model

    try:
        from qwen_tts import Qwen3TTSModel
        device = get_qwen_device()
        print(f"📦 Caricamento del modello Qwen3-TTS '{model_name}' su {device}...")
        
        # Carica il modello
        _qwen_model = Qwen3TTSModel.from_pretrained(model_name)
        
        # Sposta sul device se supportato e non automatico
        if hasattr(_qwen_model, "to"):
            _qwen_model = _qwen_model.to(device)
            
        print("✅ Modello Qwen3-TTS caricato con successo.")
        return _qwen_model
    except Exception as e:
        print(f"❌ Errore critico nel caricamento di Qwen3-TTS: {e}")
        raise e

def generate_voice_design_segment(text: str, instruct: str, output_path: str) -> bool:
    """
    Sintetizza un segmento vocale in base a una descrizione testuale della voce (Voice Design).
    
    Args:
        text: Il testo da pronunciare.
        instruct: La descrizione testuale della voce (es. "A calm Italian man with a deep voice").
        output_path: Il percorso del file WAV in cui salvare l'audio.
    """
    try:
        model = load_qwen_model()
        print(f"🎙️ Qwen3-TTS: Genero audio per '{text[:40]}...'")
        print(f"🎨 Istruzione vocale: '{instruct}'")
        
        # Genera l'audio
        audio_output = model.generate_voice_design(
            text=text,
            instruct=instruct,
            lang="it" # Forza l'italiano per NewsicaTV
        )
        
        sample_rate = 24000
        
        # Salva l'audio su disco
        if isinstance(audio_output, tuple):
            # Qwen3-TTS restituisce (list_of_numpy_arrays, sample_rate)
            raw_audio = audio_output[0]
            if len(audio_output) > 1 and isinstance(audio_output[1], int):
                sample_rate = audio_output[1]
                
            if isinstance(raw_audio, list):
                if len(raw_audio) > 0 and isinstance(raw_audio[0], np.ndarray):
                    samples = np.concatenate(raw_audio, axis=0)
                else:
                    samples = np.array(raw_audio)
            elif hasattr(raw_audio, "numpy"):
                samples = raw_audio.cpu().numpy()
            else:
                samples = np.array(raw_audio)
        elif hasattr(audio_output, "numpy"):
            samples = audio_output.cpu().numpy()
        elif isinstance(audio_output, np.ndarray):
            samples = audio_output
        else:
            samples = np.array(audio_output)
                
        sf.write(output_path, samples, sample_rate)
        print(f"✅ Segmento salvato in {output_path} (SR: {sample_rate}Hz)")
        return True
    except Exception as e:
        print(f"❌ Errore durante la sintesi vocale con Qwen3-TTS (Voice Design): {e}")
        return False
