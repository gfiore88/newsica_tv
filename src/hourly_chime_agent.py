"""
hourly_chime_agent.py — Rintocco Orario NewsicaTV
Genera un annuncio TTS una volta all'ora, a un minuto casuale stabile,
e lo invia al director come overlay musicale non interrompente.
"""

import os
import sys
import time
import datetime
import random
import fcntl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
CHIME_AUDIO_FILE = os.path.join(TMP_DIR, "hourly_chime.wav")
CHIME_VOICE_AUDIO_FILE = os.path.join(TMP_DIR, "hourly_chime_voice.wav")

# Stessa coppia onnx/voices usata dal TTS principale
KOKORO_ONNX = os.path.join(BASE_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(BASE_DIR, "voices-v1.0.bin")

# Voce istituzionale — stessa dell'anchor news
CHIME_VOICE = "if_sara"
CHIME_SPEED = 0.95
CHIME_GENERATION_LEAD_SECONDS = 35
CHIME_MINUTE_MIN = 7
CHIME_MINUTE_MAX = 53

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

NUMBER_WORDS = {
    0: "zero",
    1: "uno",
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
    12: "dodici",
    13: "tredici",
    14: "quattordici",
    15: "quindici",
    16: "sedici",
    17: "diciassette",
    18: "diciotto",
    19: "diciannove",
    20: "venti",
    30: "trenta",
    40: "quaranta",
    50: "cinquanta",
}

CHIME_TEMPLATES = [
    "Sono le {ora} in punto. Continuate a seguire NewsicaTV.",
    "Le {ora} in punto su NewsicaTV. Restiamo insieme.",
    "Sono le {ora}. NewsicaTV è con voi.",
    "Le {ora} in punto. Grazie per essere con noi su NewsicaTV.",
    "Sono le {ora} in punto, buon ascolto da NewsicaTV.",
]

_singleton_lock = None


def check_singleton(name):
    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")
    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        global _singleton_lock
        _singleton_lock = f
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
        return True
    except Exception:
        print(f"❌ ERRORE: Un'altra istanza di {name} è già in esecuzione!")
        return False

def build_chime_text(hour: int) -> str:
    ora = HOUR_WORDS.get(hour, f"{hour}")
    template = random.choice(CHIME_TEMPLATES)
    return template.format(ora=ora)


def number_to_words(value: int) -> str:
    if value in NUMBER_WORDS:
        return NUMBER_WORDS[value]
    tens = (value // 10) * 10
    unit = value % 10
    tens_word = NUMBER_WORDS.get(tens, str(tens))
    if unit in (1, 8):
        tens_word = tens_word[:-1]
    return f"{tens_word}{NUMBER_WORDS[unit]}"


def build_exact_chime_text(now=None) -> str:
    now = now or datetime.datetime.now()
    hour = now.hour
    minute = now.minute
    hour_word = HOUR_WORDS.get(hour, str(hour))

    if minute == 0:
        return build_chime_text(hour)

    minute_word = number_to_words(minute)
    if hour == 1:
        return f"È l'una e {minute_word}. NewsicaTV è con voi."
    if hour == 0:
        return f"È mezzanotte e {minute_word}. NewsicaTV è con voi."
    if hour == 12:
        return f"È mezzogiorno e {minute_word}. NewsicaTV è con voi."
    return f"Sono le {hour_word} e {minute_word}. NewsicaTV è con voi."


def generate_chime_audio(text: str, output_file=CHIME_AUDIO_FILE) -> bool:
    """Genera il file WAV del rintocco con Kokoro TTS. Ritorna True se ok.

    Nota: questa funzione viene chiamata dal generation worker sul Mac,
    NON direttamente sul VPS.
    """
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
        print(f"🔔 Generazione rintocco orario: \"{text}\"")
        kokoro = Kokoro(KOKORO_ONNX, KOKORO_VOICES)
        samples, sample_rate = kokoro.create(
            text, voice=CHIME_VOICE, speed=CHIME_SPEED, lang="it"
        )
        sf.write(output_file, samples, sample_rate)
        print(f"✅ Rintocco orario generato: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Errore generazione rintocco: {e}")
        return False


def send_chime_command(target_time=None):
    """Scrive il comando HOURLY_CHIME_READY nel file di controllo del director."""
    try:
        suffix = ""
        if target_time:
            suffix = f"|soft|{target_time.isoformat(timespec='seconds')}"
        with open(CONTROL_FILE, "w") as f:
            f.write(f"HOURLY_CHIME_READY|{CHIME_AUDIO_FILE}{suffix}")
        print(f"📡 Comando HOURLY_CHIME_READY inviato al director.")
    except Exception as e:
        print(f"❌ Errore invio comando chime: {e}")


def choose_chime_minute(hour_start: datetime.datetime) -> int:
    """Sceglie un minuto stabile per quella specifica ora locale."""
    seed = int(hour_start.strftime("%Y%m%d%H"))
    return random.Random(seed).randint(CHIME_MINUTE_MIN, CHIME_MINUTE_MAX)


def next_random_chime_time(now=None) -> datetime.datetime:
    """Restituisce il prossimo target random, evitando l'inizio/fine fascia."""
    now = now or datetime.datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    for _ in range(3):
        minute = choose_chime_minute(hour_start)
        target = hour_start.replace(minute=minute, second=0, microsecond=0)
        if target > now + datetime.timedelta(seconds=CHIME_GENERATION_LEAD_SECONDS):
            return target
        hour_start += datetime.timedelta(hours=1)

    minute = choose_chime_minute(hour_start)
    return hour_start.replace(minute=minute, second=0, microsecond=0)


def _enqueue_chime_job(text, source="automatic"):
    """Crea un generation job per il segnale orario."""
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    from newsica.storage.repositories.generation_jobs_repository import enqueue_job

    job, created = enqueue_job(
        "hourly_chime",
        priority=150,
        title="Segnale Orario Automatico",
        dedupe_key=f"hourly_chime:{source}:{datetime.datetime.now().strftime('%Y%m%d%H')}",
        payload={"text": text, "source": source, "auto_play": True},
    )
    return job, created


def _wait_for_job_ready(job_id, timeout_seconds=90):
    """Attende che il job sia completato (ready) o fallito."""
    from newsica.storage.repositories.generation_jobs_repository import get_job

    start = time.time()
    while time.time() - start < timeout_seconds:
        job = get_job(job_id)
        if not job:
            return None
        status = job.get("status", "")
        if status == "ready":
            return job
        if status in ("failed", "expired"):
            print(f"❌ Job chime {job_id} terminato con stato: {status}")
            return None
        time.sleep(3)

    print(f"⏰ Timeout attesa job chime {job_id} dopo {timeout_seconds}s.")
    return None


def run():
    print("🔔 Hourly Chime Agent avviato.")
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    while True:
        target_time = next_random_chime_time()
        generation_time = target_time - datetime.timedelta(seconds=CHIME_GENERATION_LEAD_SECONDS)
        wait = max(0.0, (generation_time - datetime.datetime.now()).total_seconds())
        print(
            f"🔔 Prossimo segnale orario alle {target_time.strftime('%H:%M')} "
            f"(generazione tra {wait:.0f} secondi)."
        )
        time.sleep(wait)

        text = build_exact_chime_text(target_time)

        # Accoda il job al generation worker (Mac) invece di generare TTS localmente
        try:
            job, created = _enqueue_chime_job(text)
            if created:
                print(f"📡 Job chime creato: {job.get('id')} — in attesa del Mac...")
            else:
                print(f"📡 Job chime già esistente: {job.get('id')}")
        except Exception as e:
            print(f"❌ Errore creazione job chime: {e}")
            time.sleep(60)
            continue

        # Attende il completamento. L'auto-play nel system_routes
        # scriverà HOURLY_CHIME_READY quando il job sarà ready.
        completed_job = _wait_for_job_ready(job.get("id"))
        if completed_job:
            print(f"✅ Segnale orario pronto e inviato al director.")
        else:
            print(f"⚠️ Segnale orario non completato in tempo. Saltato.")

        # Evita retrigger nello stesso minuto dopo restart/ritardi locali.
        time.sleep(75)


if __name__ == "__main__":
    if not check_singleton("hourly_chime_agent"):
        sys.exit(1)
    run()
