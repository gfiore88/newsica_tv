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


def write_track_metadata(
    audio_file: Path,
    *,
    title: str,
    prompt: str,
    duration: float,
    mode: str,
    theme: str | None,
):
    metadata_file = audio_file.with_suffix(".json")
    payload = {
        "title": title,
        "prompt": prompt,
        "duration": duration,
        "mode": mode,
        "theme": theme,
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "audio_file": audio_file.name,
    }
    metadata_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

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

_DIT_HANDLER = None
_LLM_HANDLER = None

def get_handlers():
    global _DIT_HANDLER, _LLM_HANDLER
    if _DIT_HANDLER is None:
        logger.info("Initializing ACE-Step 1.5 Handlers (this will download weights if missing)...")
        ace_step_path = BASE_DIR / ".external" / "ACE-Step"
        if str(ace_step_path) not in sys.path:
            sys.path.insert(0, str(ace_step_path))
        
        from acestep.handler import AceStepHandler
        from acestep.llm_inference import LLMHandler
        
        # 1. Initialize DiT handler
        _DIT_HANDLER = AceStepHandler()
        dit_status, dit_ok = _DIT_HANDLER.initialize_service(
            project_root=str(ace_step_path),
            config_path="acestep-v15-turbo",
            device="auto",
            use_flash_attention=False,
            compile_model=False,
            offload_to_cpu=False,
        )
        if not dit_ok:
            raise RuntimeError(f"Failed to initialize DiT handler: {dit_status}")
            
        # 2. Initialize LLM handler for thinking/CoT reasoning
        _LLM_HANDLER = LLMHandler()
        lm_status, lm_ok = _LLM_HANDLER.initialize(
            checkpoint_dir=str(ace_step_path / "checkpoints"),
            lm_model_path="acestep-5Hz-lm-1.7B",
            backend="mlx", # Apple Silicon MLX native acceleration
            device="auto",
            offload_to_cpu=False,
        )
        if not lm_ok:
            logger.warning(f"Failed to initialize LLM handler with MLX backend: {lm_status}. Trying fallback 'pt' backend.")
            lm_status, lm_ok = _LLM_HANDLER.initialize(
                checkpoint_dir=str(ace_step_path / "checkpoints"),
                lm_model_path="acestep-5Hz-lm-1.7B",
                backend="pt",
                device="auto",
                offload_to_cpu=False,
            )
            if not lm_ok:
                logger.warning(f"Failed to initialize fallback LLM handler: {lm_status}. Generation will proceed without thinking (fallback quality).")
                _LLM_HANDLER = None
                
    return _DIT_HANDLER, _LLM_HANDLER

def run_ace_step_generation(prompt: str, output_path: Path, duration: float = 60.0):
    """
    Esecuzione reale di ACE-Step 1.5.
    """
    logger.info(f"Running ACE-Step 1.5 generation for prompt: '{prompt}'")
    dit_handler, llm_handler = get_handlers()
    
    from acestep.inference import generate_music, GenerationParams, GenerationConfig
    
    # Estrazione automatica delle lyrics dal prompt se presenti
    lyrics = "[Instrumental]"
    instrumental = True
    prompt_lower = prompt.lower()
    if "lyrics:" in prompt_lower:
        idx = prompt_lower.find("lyrics:")
        lyrics_part = prompt[idx + len("lyrics:"):].strip()
        # Rimuoviamo eventuali sezioni successive (come Ending:, Negative prompt:)
        for stop_word in ["ending:", "negative prompt:", "negative:"]:
            stop_word_lower = stop_word.lower()
            if stop_word_lower in lyrics_part.lower():
                stop_idx = lyrics_part.lower().find(stop_word_lower)
                lyrics_part = lyrics_part[:stop_idx].strip()
        
        # Se le lyrics estratte sono valide e non indicano instrumental
        if lyrics_part and "[instrumental]" not in lyrics_part.lower() and "n/a" not in lyrics_part.lower():
            lyrics = lyrics_part
            instrumental = False
            logger.info(f"Lyrics individuate nel prompt! Lunghezza: {len(lyrics)}. Disabilitato instrumental.")
            logger.info(f"Lyrics estratte:\n{lyrics}")
            
    params = GenerationParams(
        task_type="text2music",
        caption=prompt,
        lyrics=lyrics,
        instrumental=instrumental,
        duration=duration,
        inference_steps=12, # Optimized for higher quality while remaining fast
        shift=3.0,          # Recommended for turbo models in ACE-Step 1.5 docs
        seed=random.randint(0, 2**32 - 1),
        enable_normalization=True,
        normalization_db=-1.0,
        thinking=(llm_handler is not None),
    )
    
    config = GenerationConfig(
        batch_size=1,
        use_random_seed=False,
        audio_format="wav",
    )
    
    result = generate_music(
        dit_handler=dit_handler,
        llm_handler=llm_handler,
        params=params,
        config=config,
        save_dir=str(output_path.parent),
    )
    
    if not result.success:
        raise RuntimeError(f"Generation failed: {result.error}")
        
    if not result.audios:
        raise RuntimeError("Generation succeeded but no audio files were generated.")
        
    generated_file_path = Path(result.audios[0]["path"])
    logger.info(f"Generated track at: {generated_file_path}")
    
    # Move/rename the generated file to the desired output_path
    if generated_file_path.exists() and generated_file_path != output_path:
        if output_path.exists():
            output_path.unlink()
        generated_file_path.rename(output_path)

def normalize_audio(input_path: Path, output_path: Path, duration: float = 180.0):
    """
    Normalizza il file audio a livelli TV broadcast (es -23 LUFS) usando FFmpeg.
    """
    logger.info(f"Normalizing audio: {input_path.name} with duration={duration}s")
    # Calcolo dinamico del tempo di inizio del fadeout (st = duration - 6 per sfumare per 5 secondi terminando 1 secondo prima della fine reale)
    st = max(0.0, duration - 6.0)
    cmd = f'ffmpeg -y -i "{input_path}" -ar 44100 -ac 2 -af "loudnorm=I=-14:TP=-1:LRA=11,afade=t=out:st={st}:d=5" "{output_path}" -nostats -loglevel error'
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
        # Ordina i brani per data di modifica, dal più vecchio al più recente
        current_tracks.sort(key=lambda p: p.stat().st_mtime)
        # Elimina i brani più vecchi per fare spazio al nuovo
        num_to_delete = len(current_tracks) - MAX_TRACKS + 1
        for i in range(num_to_delete):
            oldest_track = current_tracks[i]
            logger.info(f"Cache limit reached ({len(current_tracks)}/{MAX_TRACKS}). Deleting oldest track: {oldest_track.name}")
            try:
                oldest_track.unlink(missing_ok=True)
                oldest_track.with_suffix(".json").unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to delete oldest track {oldest_track.name}: {e}")
        
    time_of_day = get_time_of_day()
    fallback_prompts = load_prompts()
    
    # Selezioniamo un fallback prompt statico nel caso in cui Ollama fallisca
    if time_of_day in fallback_prompts and fallback_prompts[time_of_day]:
        fallback_prompt = random.choice(fallback_prompts[time_of_day])
    else:
        fallback_prompt = "instrumental, background music, calm, clean production"
        
    # Recupera il tema attivo per lo slot corrente dal palinsesto
    theme = None
    try:
        from newsica.broadcast.scheduler import get_wallclock_schedule_key
        from schedule_generator import get_current_schedule
        schedule_data = get_current_schedule()
        current_key = get_wallclock_schedule_key()
        current_block = schedule_data.get(current_key, {})
        theme = current_block.get("theme", None)
        logger.info(f"Rilevato tema per lo slot orario '{current_key}': {theme}")
    except Exception as e:
        logger.warning(f"Impossibile leggere il tema dal palinsesto: {e}")

    director = EditorialDirectorAgent()
    prompt_data = director.generate_music_prompt(time_of_day, fallback_prompt, theme=theme)
    
    if isinstance(prompt_data, dict):
        prompt = prompt_data.get("prompt", fallback_prompt)
        duration = prompt_data.get("duration", 180.0)
        mode = prompt_data.get("mode", "vocal_hook")
        title = prompt_data.get("title", "Newsica AI Track")
    else:
        prompt = prompt_data
        duration = 180.0
        mode = "instrumental"
        title = "Newsica AI Track"

    logger.info(f"Prompt selezionato per la generazione (modalità: {mode}, durata: {duration}s, titolo: '{title}')")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file = TMP_DIR / f"temp_ai_gen_{timestamp}.wav"
    final_file = AI_MUSIC_DIR / f"ai_track_{timestamp}.wav"
    
    try:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        run_ace_step_generation(prompt, temp_file, duration=duration)
        if temp_file.exists():
            normalize_audio(temp_file, final_file, duration=duration)
            write_track_metadata(
                final_file,
                title=title,
                prompt=prompt,
                duration=duration,
                mode=mode,
                theme=theme,
            )
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
