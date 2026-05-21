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
import fcntl
from datetime import datetime
from pathlib import Path

# Configura logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (AiMusicGen) %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets"
AI_MUSIC_DIR = ASSETS_DIR / "ai_music"
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
    
    params = (
        30.0,            # audio_duration
        prompt,          # prompt
        "",              # lyrics
        27,              # infer_step
        3.5,             # guidance_scale
        "euler",         # scheduler_type
        "none",          # cfg_type
        1.0,             # omega_scale
        "42",            # actual_seeds
        0.5,             # guidance_interval
        1.0,             # guidance_interval_decay
        1.5,             # min_guidance_scale
        False,           # use_erg_tag
        False,           # use_erg_lyric
        False,           # use_erg_diffusion
        "1",             # oss_steps
        0.0,             # guidance_scale_text
        0.0,             # guidance_scale_lyric
    )
    
    pipeline(*params, save_path=str(output_path))
    logger.info(f"Generated raw file at {output_path}")

def normalize_audio(input_path: Path, output_path: Path):
    """
    Normalizza il file audio a livelli TV broadcast (es -23 LUFS) usando FFmpeg.
    """
    logger.info(f"Normalizing audio: {input_path.name}")
    # Esempio: usiamo ffmpeg per normalizzare (loudnorm)
    cmd = f'ffmpeg -y -i "{input_path}" -af loudnorm=I=-23:TP=-2:LRA=11 "{output_path}" -nostats -loglevel error'
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
        
    tod = get_time_of_day()
    prompts_data = load_prompts()
    prompts = prompts_data.get(tod, ["Default lofi news background"])
    prompt = random.choice(prompts)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file = ASSETS_DIR / f"temp_ai_gen_{timestamp}.wav"
    final_file = AI_MUSIC_DIR / f"ai_track_{timestamp}.wav"
    
    try:
        run_ace_step_generation(prompt, temp_file)
        if temp_file.exists():
            normalize_audio(temp_file, final_file)
            logger.info(f"Successfully added {final_file.name} to library.")
            return True
    except Exception as e:
        logger.error(f"Failed to generate AI music: {e}")
        if temp_file.exists():
            os.remove(temp_file)
            
    return False

def acquire_lock():
    lockfile = BASE_DIR / "tmp" / "ai_music.lock"
    try:
        lock_fd = os.open(lockfile, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (IOError, OSError):
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    
    lock_fd = acquire_lock()
    if lock_fd is None:
        logger.info("Generation already in progress. Exiting.")
        sys.exit(0)
        
    try:
        generate_track()
    finally:
        os.close(lock_fd)
