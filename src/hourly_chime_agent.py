"""
hourly_chime_agent.py — Rintocco Orario NewsicaTV
Genera ogni ora in punto un annuncio TTS "Sono le X in punto su NewsicaTV"
e lo invia al director come interrupt prioritario (analogo alla Breaking News).
"""

import os
import sys
import time
import datetime
import soundfile as sf

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
CHIME_AUDIO_FILE = os.path.join(TMP_DIR, "hourly_chime.wav")

# Stessa coppia onnx/voices usata dal TTS principale
KOKORO_ONNX = os.path.join(BASE_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(BASE_DIR, "voices-v1.0.bin")

# Voce istituzionale — stessa dell'anchor news
CHIME_VOICE = "if_sara"
CHIME_SPEED = 0.95

HOUR_WORDS = {
    0: "mezzanotte",
    1: "una",
    2: "due",
    3: "tre",
    4: "quattro",
    5: "cinque",
    6: "sei",
    7: "sette",
    8: "otto",
    9: "nove",
    10: "dieci",
    11: "undici",
    12: "mezzogiorno",
    13: "tredici",
    14: "quattordici",
    15: "quindici",
    16: "sedici",
    17: "diciassette",
    18: "diciotto",
    19: "diciannove",
    20: "venti",
    21: "ventuno",
    22: "ventidue",
    23: "ventitre",
}

CHIME_TEMPLATES = [
    "Sono le {ora} in punto. Continuate a seguire NewsicaTV.",
    "Le {ora} in punto su NewsicaTV. Restiamo insieme.",
    "Sono le {ora}. NewsicaTV è con voi.",
    "Le {ora} in punto. Grazie per essere con noi su NewsicaTV.",
    "Sono le {ora} in punto, buon ascolto da NewsicaTV.",
]

import random


def build_chime_text(hour: int) -> str:
    ora = HOUR_WORDS.get(hour, f"{hour}")
    template = random.choice(CHIME_TEMPLATES)
    return template.format(ora=ora)


def generate_chime_audio(text: str) -> bool:
    """Genera il file WAV del rintocco con Kokoro TTS. Ritorna True se ok."""
    try:
        from kokoro_onnx import Kokoro
        print(f"🔔 Generazione rintocco orario: \"{text}\"")
        kokoro = Kokoro(KOKORO_ONNX, KOKORO_VOICES)
        samples, sample_rate = kokoro.create(
            text, voice=CHIME_VOICE, speed=CHIME_SPEED, lang="it"
        )
        sf.write(CHIME_AUDIO_FILE, samples, sample_rate)
        print(f"✅ Rintocco orario generato: {CHIME_AUDIO_FILE}")
        return True
    except Exception as e:
        print(f"❌ Errore generazione rintocco: {e}")
        return False


def send_chime_command():
    """Scrive il comando HOURLY_CHIME_READY nel file di controllo del director."""
    try:
        with open(CONTROL_FILE, "w") as f:
            f.write(f"HOURLY_CHIME_READY|{CHIME_AUDIO_FILE}")
        print(f"📡 Comando HOURLY_CHIME_READY inviato al director.")
    except Exception as e:
        print(f"❌ Errore invio comando chime: {e}")


def seconds_to_next_hour() -> float:
    """Calcola i secondi mancanti alla prossima ora intera, con 3s di anticipo
    per compensare il tempo di generazione TTS."""
    now = datetime.datetime.now()
    next_hour = (now + datetime.timedelta(hours=1)).replace(
        minute=0, second=0, microsecond=0
    )
    delta = (next_hour - now).total_seconds()
    # Inizia la generazione TTS ~8 secondi prima dell'ora per essere pronti
    return max(0.0, delta - 8.0)


def run():
    print("🔔 Hourly Chime Agent avviato.")
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    while True:
        wait = seconds_to_next_hour()
        print(f"🔔 Prossimo rintocco tra {wait:.0f} secondi.")
        time.sleep(wait)

        # Ora siamo ~8 secondi prima del rintocco: generiamo l'audio
        target_hour = (datetime.datetime.now() + datetime.timedelta(seconds=10)).hour
        text = build_chime_text(target_hour)

        ok = generate_chime_audio(text)
        if not ok:
            # Aspetta qualche secondo e riprova al prossimo minuto
            time.sleep(60)
            continue

        # Attendiamo il momento esatto (ore precise ±1s)
        now = datetime.datetime.now()
        on_the_hour = now.replace(minute=0, second=0, microsecond=0)
        if now > on_the_hour:
            on_the_hour += datetime.timedelta(hours=1)
        remaining = (on_the_hour - datetime.datetime.now()).total_seconds()
        if remaining > 0:
            time.sleep(remaining)

        send_chime_command()

        # Evita di ritriggerare subito dopo (attendiamo 90s)
        time.sleep(90)


if __name__ == "__main__":
    run()
