import re


def prepare_text_for_tts(text, keep_brackets=False):
    # Gestione indicazioni tra parentesi o asterischi per non farle leggere letteralmente
    if keep_brackets:
        # Per Qwen3-TTS: normalizza gli altri tag (tonde, graffe, asterischi) in parentesi quadre per farli interpretare
        text = re.sub(r"\(([^)]+)\)", r"[\1]", text)
        text = re.sub(r"\{([^}]+)\}", r"[\1]", text)
        text = re.sub(r"\*([^*]+)\*", r"[\1]", text)
    else:
        # Per Kokoro: rimuove indicazioni tra parentesi quadre, tonde, graffe o asterischi
        text = re.sub(r"\[[^\]]+\]", "", text)
        text = re.sub(r"\([^)]+\)", "", text)
        text = re.sub(r"\{[^}]+\}", "", text)
        text = re.sub(r"\*[^*]+\*", "", text)
    
    # Rimuove eventuali asterischi o parentesi rimaste orfane per sicurezza
    text = re.sub(r"\*+", "", text)
    
    text = re.sub(r"\s+", " ", text)
    text = text.replace("...", ". ")
    text = text.replace(" km/h", " chilometri orari")
    text = text.replace("°C", " gradi")
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([.!?])\s+", r"\1\n\n", text)
    return text.strip()

