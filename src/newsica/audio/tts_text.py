import re


def prepare_text_for_tts(text):
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("...", ". ")
    text = text.replace(" km/h", " chilometri orari")
    text = text.replace("°C", " gradi")
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([.!?])\s+", r"\1\n\n", text)
    return text.strip()

