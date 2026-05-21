#!/usr/bin/env python3
"""
AI Music Generator wrapper per ACE-Step.
Genera brani asincroni per popolare assets/ai_music/ in background.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

# Aggiungiamo src al path per poter importare gli agenti
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))
from newsica.agents.editorial_director import EditorialDirectorAgent

# Configura logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (AiMusicGen) %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets"
AI_MUSIC_DIR = ASSETS_DIR / "ai_music"
TMP_DIR = BASE_DIR / "tmp"
PROMPTS_FILE = BASE_DIR / "src" / "newsica" / "editorial" / "prompts" / "music.json"

MAX_TRACKS = 20  # Quanti brani mantenere in cache

def get_time_of_day():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    else:
        return "evening"

def load_prompts():
    if not PROMPTS_FILE.exists():
        return {"morning": ["Lofi chill"], "afternoon": ["Lofi chill"], "evening": ["Lofi chill"]}
    with open(PROMPTS_FILE, "r") as f:
        return json.load(f)

_PIPELINE = None

def get_pipeline():
    global _PIPELINE
    if _PIPELINE is None:
        logger.info("Initializing ACEStepPipeline (this will download weights if missing)...")
        ace_step_path = BASE_DIR / ".external" / "ACE-Step"
        if str(ace_step_path) not in sys.path:
            sys.path.insert(0, str(ace_step_path))
        from acestep.pipeline_ace_step import ACEStepPipeline
        
        _PIPELINE = ACEStepPipeline(
            checkpoint_dir=None, # auto download
            dtype="float32",
            torch_compile=False,
        )
    return _PIPELINE

def run_ace_step_generation(prompt: str, output_path: Path):
    """
    Esecuzione reale di ACE-Step.
    """
    logger.info(f"Running ACE-Step generation for prompt: '{prompt}'")
    pipeline = get_pipeline()
    
    kwargs = {
        "audio_duration": 60.0,
        "prompt": prompt,
        "lyrics": "",
        "infer_step": 60,
        "guidance_scale": 15.0,
        "scheduler_type": "euler",
        "cfg_type": "apg",
        "omega_scale": 10.0,
        "manual_seeds": [random.randint(0, 4294967295)],
        "guidance_interval": 0.5,
        "guidance_interval_decay": 0.0,
        "min_guidance_scale": 3.0,
        "use_erg_tag": True,
        "use_erg_lyric": False,
        "use_erg_diffusion": True,
        "oss_steps": "",
        "guidance_scale_text": 0.0,
        "guidance_scale_lyric": 0.0,
        "save_path": str(output_path),
        "format": "wav"
    }
    
    pipeline(**kwargs)
    logger.info(f"Generated raw file at {output_path}")

def normalize_audio(input_path: Path, output_path: Path):
    """
    Normalizza il file audio a livelli TV broadcast (es -23 LUFS) usando FFmpeg.
    """
    logger.info(f"Normalizing audio: {input_path.name}")
    # Esempio: usiamo ffmpeg per normalizzare (loudnorm), abbassare il bitrate a 24000 Hz Mono, e fare un fadeout di 5 secondi alla fine
    cmd = f'ffmpeg -y -i "{input_path}" -ar 24000 -ac 1 -af "loudnorm=I=-14:TP=-1:LRA=11,afade=t=out:st=54:d=5" "{output_path}" -nostats -loglevel error'
    res = os.system(cmd)
    if res != 0:
        logger.error("FFmpeg normalization failed. Saving raw instead.")
        os.rename(input_path, output_path)
    else:
        os.remove(input_path)

def generate_track():
    AI_MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    
    current_tracks = list(AI_MUSIC_DIR.glob("*.wav"))
    if len(current_tracks) >= MAX_TRACKS:
        logger.info(f"Cache is full ({len(current_tracks)}/{MAX_TRACKS}). Skipping generation.")
        return False
        
    time_of_day = get_time_of_day()
    fallback_prompts = load_prompts()
    
    # Selezioniamo un fallback prompt statico nel caso in cui Ollama fallisca
    if time_of_day in fallback_prompts and fallback_prompts[time_of_day]:
        fallback_prompt = random.choice(fallback_prompts[time_of_day])
    else:
        fallback_prompt = "instrumental, background music, calm, clean production"
        
    prompt = None
    if not prompt:
        director = EditorialDirectorAgent()
        prompt = director.generate_music_prompt(time_of_day, fallback_prompt)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file = TMP_DIR / f"temp_ai_gen_{timestamp}.wav"
    final_file = AI_MUSIC_DIR / f"ai_track_{timestamp}.wav"
    
    try:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        run_ace_step_generation(prompt, temp_file)
        if temp_file.exists():
            normalize_audio(temp_file, final_file)
            logger.info(f"Successfully added {final_file.name} to library.")
            
            # Pulizia file temporanei
            try:
                temp_file.unlink(missing_ok=True)
                json_params = temp_file.with_name(f"{temp_file.stem}_input_params.json")
                json_params.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")
            
            return True
        else:
            logger.error("ACE-Step generation failed (no output file).")
            return False
    except Exception as e:
        logger.error(f"Failed to generate AI music: {e}")
        if temp_file.exists():
            os.remove(temp_file)
            
    return False

def acquire_lock():
    """Lock basato su PID: se il processo proprietario è morto, rimuove il lock orfano."""
    lockfile = BASE_DIR / "tmp" / "ai_music.lock"
    try:
        # Se il lockfile esiste, verifica se il processo è ancora vivo
        if lockfile.exists():
            try:
                pid = int(lockfile.read_text().strip())
                # Controlla se il processo con quel PID esiste ancora
                os.kill(pid, 0)  # Signal 0 = solo controllo esistenza
                # Il processo è ancora vivo → generazione in corso, esci
                logger.info(f"Generazione già in corso (PID {pid}). Esco.")
                return None
            except (ValueError, ProcessLookupError, PermissionError):
                # PID non valido o processo morto → lock orfano, lo rimuoviamo
                logger.warning("Lock orfano rilevato. Rimosso e riprendo.")
                lockfile.unlink(missing_ok=True)
        
        # Scrivi il nostro PID nel lockfile
        lockfile.write_text(str(os.getpid()))
        return True
    except Exception as e:
        logger.error(f"Errore durante l'acquisizione del lock: {e}")
        return None

def release_lock():
    """Rimuove il lockfile al termine della generazione."""
    lockfile = BASE_DIR / "tmp" / "ai_music.lock"
    try:
        lockfile.unlink(missing_ok=True)
    except Exception:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    
    lock = acquire_lock()
    if lock is None:
        sys.exit(0)
        
    try:
        generate_track()
    finally:
        release_lock()
