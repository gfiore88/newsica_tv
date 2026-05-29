import os
import re
import json
import subprocess
import requests
import soundfile as sf
import numpy as np
from pathlib import Path

from newsica.config.paths import TMP_DIR
from newsica.audio.tts_text import prepare_text_for_tts
from newsica.editorial.fact_checker import check_hallucinations, silent_scrub
from newsica.editorial.podcast_contract import (
    build_podcast_revision_prompt,
    validate_podcast_script,
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))
PODCAST_OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_PODCAST_TIMEOUT", str(max(OLLAMA_TIMEOUT, 120))))
PODCAST_NUM_PREDICT = int(os.getenv("OLLAMA_PODCAST_NUM_PREDICT", "1400"))

BASE_DIR = Path(__file__).parent.parent.parent.parent
CHATTERBOX_PYTHON = os.getenv("CHATTERBOX_PYTHON", str(BASE_DIR / ".venv_tts_spike" / "bin" / "python"))
CHATTERBOX_SCRIPT = str(BASE_DIR / "src" / "newsica" / "audio" / "chatterbox_tts.py")

class AIIntegratorAgent:
    def __init__(self, work_dir=TMP_DIR):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_script(self, content_data):
        """Genera lo script usando Ollama"""
        print(f"Avvio rielaborazione editoriale tramite LLM (Ollama locale) per {content_data['character_id']}...")

        is_podcast = content_data["character_id"] == "podcast"
        base_prompt = content_data["prompt"]
        max_attempts = 4 if is_podcast else 3

        payload = {
            "model": MODEL_NAME,
            "system": content_data["system_prompt"],
            "prompt": base_prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.4,
                "num_predict": PODCAST_NUM_PREDICT if is_podcast else 700,
            },
        }

        script = ""
        is_safe = True
        bad_entities = []
        extra_instructions = []

        for attempt in range(max_attempts):
            try:
                payload["prompt"] = base_prompt
                if extra_instructions:
                    payload["prompt"] += "\n\n" + "\n\n".join(extra_instructions)

                timeout = PODCAST_OLLAMA_TIMEOUT if is_podcast else OLLAMA_TIMEOUT
                response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
                response.raise_for_status()
                script = response.json().get("response", "").strip()
                if not script:
                    print(f"⚠️ [{attempt+1}/{max_attempts}] Ollama ha restituito un copione vuoto.")
                    continue

                if is_podcast:
                    is_valid_podcast, validation_issues = validate_podcast_script(script)
                    if not is_valid_podcast:
                        print(
                            f"⚠️ [{attempt+1}/{max_attempts}] Copione podcast non valido: "
                            f"{'; '.join(validation_issues)}"
                        )
                        extra_instructions = [build_podcast_revision_prompt(validation_issues)]
                        continue

                # Fact Checking
                is_safe, bad_entities = check_hallucinations(script, base_prompt)
                if not is_safe:
                    print(f"🚨 [{attempt+1}/{max_attempts}] ALLUCINAZIONE RILEVATA nel copione di {content_data['character_id']}: {bad_entities}")
                    extra_instructions = []
                    if is_podcast:
                        is_valid_podcast, validation_issues = validate_podcast_script(script)
                        if not is_valid_podcast:
                            extra_instructions.append(build_podcast_revision_prompt(validation_issues))
                    extra_instructions.append(
                        "ATTENZIONE: Nel tuo precedente tentativo hai inventato questi dati/numeri: "
                        + ", ".join(bad_entities)
                        + ". Riscrivi il copione assicurandoti di usare SOLO dati presenti nel JSON fornito e senza inventare nulla."
                    )
                    continue

                # Se è sicuro
                is_safe = True
                break

            except requests.exceptions.RequestException as e:
                print(f"❌ Errore connessione a Ollama: {e}")
                break
                
        if not is_safe and script:
            print("🧽 [AIIntegratorAgent] Tentativi esauriti. Applico Silent Scrubbing per rimuovere le allucinazioni.")
            script = silent_scrub(script, bad_entities)

        if is_podcast and script:
            is_valid_podcast, validation_issues = validate_podcast_script(script)
            if not is_valid_podcast:
                print(
                    "⚠️ [AIIntegratorAgent] Copione podcast ancora non valido dopo i tentativi: "
                    + "; ".join(validation_issues)
                    + ". Uso fallback locale."
                )
                script = ""

        if not script:
            print("⚠️ Uso copione fallback locale.")
            script = content_data["fallback_script"]
            
        # Aggiungi intro se presente
        if content_data.get("intro"):
            script = f"{content_data['intro']}\n\n{script}"
            
        script_file = self.work_dir / "script.txt"
        script_file.write_text(script, encoding="utf-8")
        return script

    def parse_speaker_segments(self, raw_text):
        pattern = re.compile(r'\[SPEAKER:\s*([^\]]+)\]')
        matches = list(pattern.finditer(raw_text))
        segments = []

        if not matches:
            print("⚠️ Attenzione: Nessun tag SPEAKER rilevato. Uso Giulia come conduttrice di default.")
            return [("Giulia", raw_text)]

        for idx, match in enumerate(matches):
            speaker = match.group(1).strip()
            start_idx = match.end()
            end_idx = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_text)
            text_content = raw_text[start_idx:end_idx].strip()
            if text_content:
                segments.append((speaker, text_content))

        return segments

    def _generate_podcast(self, segments):
        # Utilizza il subprocess verso tts_generator.py o riusa logica qui?
        # Per semplicità invochiamo tts_generator.py per ora, ma l'obiettivo è
        # assorbire la logica. Visto che Kokoro_onnx è installato globalmente.
        pass

    def generate_audio(self, script_text, content_data):
        """
        Sintetizza l'audio a partire dallo script.
        Restituisce una lista di path (Path) ai file generati.
        """
        script_file = self.work_dir / "script.txt"
        script_file.write_text(script_text, encoding="utf-8")
        
        # Pulizia pre-generazione in work_dir
        for f in self.work_dir.glob("audio*.wav"):
            f.unlink()
        if (self.work_dir / "is_multipart.txt").exists():
            (self.work_dir / "is_multipart.txt").unlink()
            
        import sys
        PYTHON_EXEC = sys.executable
        tts_script = BASE_DIR / "src" / "tts_generator.py"
        
        print("Sintesi vocale (TTS)...")
        # Inseriamo NEWSICA_TMP_DIR nell'ambiente del subprocess
        import os
        env = os.environ.copy()
        env["NEWSICA_TMP_DIR"] = str(self.work_dir.resolve())
        
        subprocess.run([str(PYTHON_EXEC), str(tts_script), content_data["character_id"]], env=env, check=True)
        
        generated_files = []
        if (self.work_dir / "audio.wav").exists():
            generated_files.append(self.work_dir / "audio.wav")
            
        # Validazione rigorosa dei file per show multi-part
        multipart_indicator = self.work_dir / "is_multipart.txt"
        if multipart_indicator.exists():
            try:
                with multipart_indicator.open("r", encoding="utf-8") as f:
                    num_parts = int(f.read().strip())
                print(f"🕵️‍♂️ [AIIntegratorAgent] Rilevato show multi-part. Verifico l'esistenza di {num_parts} parti...")
                for i in range(1, num_parts + 1):
                    part_file = self.work_dir / f"audio_part{i}.wav"
                    if not part_file.exists():
                        raise RuntimeError(f"Errore di validazione: file multi-part '{part_file.name}' atteso ma non generato/mancante.")
                    generated_files.append(part_file)
                generated_files.append(multipart_indicator)
                print(f"✅ [AIIntegratorAgent] Validazione multi-part completata! Trovate tutte le {num_parts} parti.")
            except Exception as e:
                print(f"❌ [AIIntegratorAgent] Errore di validazione dei file audio generati: {e}")
                raise
        else:
            for f in self.work_dir.glob("audio_part*.wav"):
                generated_files.append(f)
            
        return generated_files
