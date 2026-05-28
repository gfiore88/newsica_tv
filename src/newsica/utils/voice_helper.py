import re
import numpy as np

# Mappe di miscelazione (Blending) stabili per Kokoro ONNX
CHARACTER_VOICE_BLENDS = {
    # Chiara
    "chiara": [("if_sara", 1.0)],
    "news": [("if_sara", 1.0)],
    "breaking_news": [("if_sara", 1.0)],
    "breaking": [("if_sara", 1.0)],
    
    # Maya
    "maya": [("if_sara", 0.65), ("af_sky", 0.35)],
    "wellness": [("if_sara", 0.65), ("af_sky", 0.35)],
    
    # Leo
    "leo": [("im_nicola", 0.60), ("am_adam", 0.40)],
    "sport": [("im_nicola", 0.60), ("am_adam", 0.40)],
    
    # Giorgio
    "giorgio": [("im_nicola", 0.70), ("am_onyx", 0.30)],
    "motori": [("im_nicola", 0.70), ("am_onyx", 0.30)],
    
    # Colonnello
    "colonnello": [("im_nicola", 0.55), ("am_michael", 0.45)],
    "meteo": [("im_nicola", 0.55), ("am_michael", 0.45)],
}

def normalize_key(key: str) -> str:
    if not key:
        return ""
    return re.sub(r'[^a-zA-Z0-9_]', '', str(key)).lower().strip()

def get_voice_style_for_character(kokoro, character_id_or_name: str) -> np.ndarray | str:
    """
    Ritorna lo stile vocale (come np.ndarray) personalizzato per il personaggio o la rubrica passata.
    Utilizza la miscelazione (Blending) lineare dei vettori di stile del modello per cambiare timbro in modo drastico.
    Se il personaggio non è mappato, ritorna la voce base come stringa.
    """
    key = normalize_key(character_id_or_name)
    blend_config = CHARACTER_VOICE_BLENDS.get(key)
    
    if not blend_config:
        # Fallback sicuro
        if "sara" in key or "femm" in key or "female" in key:
            return "if_sara"
        return "im_nicola"
        
    # Ottimizzazione: se c'è solo una voce con peso 1.0, ritorna direttamente il nome per velocità
    if len(blend_config) == 1 and blend_config[0][1] == 1.0:
        return blend_config[0][0]
        
    try:
        style = None
        for voice_name, weight in blend_config:
            v_style = kokoro.get_voice_style(voice_name)
            if style is None:
                style = v_style * weight
            else:
                style += v_style * weight
        return style.astype(np.float32)
    except Exception as e:
        print(f"⚠️ Errore durante la miscelazione della voce per '{character_id_or_name}': {e}. Fallback alla voce base.")
        # Ritorna la prima voce del blend come fallback sicuro
        return blend_config[0][0]
