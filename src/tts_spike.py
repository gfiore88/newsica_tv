from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "tmp" / "tts_spike"
DEFAULT_SCRIPT = """[SPEAKER: Giulia] Benvenuti a Newsica Talk. Oggi facciamo una prova tecnica: vogliamo capire se una voce sintetica riesce a sembrare naturale in italiano, senza effetto lettura.
[SPEAKER: Marco] Esatto. La sfida vera non e' solo pronunciare bene le parole, ma mantenere ritmo, pause e identita' dei due speaker durante una conversazione.
[SPEAKER: Giulia] E soprattutto dobbiamo capire se il modello gestisce davvero il dialogo multi-speaker, oppure se dobbiamo costruire noi una pipeline a turni.
[SPEAKER: Marco] Questo test ci serve proprio a scegliere con orecchio critico, non solo leggendo le promesse dei modelli."""


@dataclass
class Segment:
    speaker: str
    text: str


@dataclass
class Result:
    engine: str
    label: str
    status: str
    output: str | None
    seconds: float | None
    notes: str


def parse_script(script: str) -> list[Segment]:
    import re

    pattern = re.compile(r"\[SPEAKER:\s*([^\]]+)\]")
    matches = list(pattern.finditer(script))
    if not matches:
        return [Segment("Giulia", script.strip())] if script.strip() else []

    segments: list[Segment] = []
    for idx, match in enumerate(matches):
        speaker = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(script)
        text = script[start:end].strip()
        if text:
            segments.append(Segment(speaker, text))
    return segments


def combine_wavs(paths: list[Path], output_path: Path, pause_seconds: float = 0.25) -> None:
    arrays: list[np.ndarray] = []
    sample_rate: int | None = None

    for path in paths:
        data, sr = sf.read(path, dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        if sample_rate is None:
            sample_rate = sr
        elif sr != sample_rate:
            raise RuntimeError(f"Sample rate mismatch: {path} has {sr}, expected {sample_rate}")
        if arrays:
            arrays.append(np.zeros(int(sample_rate * pause_seconds), dtype=np.float32))
        arrays.append(data)

    if not arrays or sample_rate is None:
        raise RuntimeError("No audio segments generated")
    sf.write(output_path, np.concatenate(arrays), sample_rate)


def write_error_audio(path: Path, sample_rate: int = 24000) -> None:
    sf.write(path, np.zeros(sample_rate // 2, dtype=np.float32), sample_rate)


def run_kyutai(segments: list[Segment], output_path: Path) -> str:
    try:
        from pocket_tts import TTSModel
    except Exception as exc:
        raise RuntimeError("Pocket TTS non installato. Installa con: venv/bin/pip install pocket-tts") from exc

    import scipy.io.wavfile

    model = TTSModel.load_model(language=os.getenv("SPIKE_KYUTAI_LANGUAGE", "italian_24l"))
    voices = {
        "giulia": os.getenv("SPIKE_KYUTAI_GIULIA_VOICE", os.getenv("SPIKE_GIULIA_VOICE", "lola")),
        "marco": os.getenv("SPIKE_KYUTAI_MARCO_VOICE", os.getenv("SPIKE_MARCO_VOICE", "giovanni")),
    }
    voice_states: dict[str, object] = {}
    segment_paths: list[Path] = []

    for idx, segment in enumerate(segments, start=1):
        key = segment.speaker.lower()
        voice = voices.get(key, os.getenv("SPIKE_DEFAULT_VOICE", "giovanni"))
        if voice not in voice_states:
            voice_states[voice] = model.get_state_for_audio_prompt(voice)
        audio = model.generate_audio(voice_states[voice], segment.text)
        segment_path = output_path.with_name(f"{output_path.stem}_seg{idx}.wav")
        scipy.io.wavfile.write(segment_path, model.sample_rate, audio.detach().cpu().numpy())
        segment_paths.append(segment_path)

    combine_wavs(segment_paths, output_path)
    return "Kyutai Pocket TTS: turn stitching locale. Usa SPIKE_KYUTAI_GIULIA_VOICE/SPIKE_KYUTAI_MARCO_VOICE per voci catalogo o reference abilitati."


def run_chatterbox(segments: list[Segment], output_path: Path) -> str:
    try:
        import torch
        import torchaudio as ta
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    except Exception as exc:
        raise RuntimeError(
            "Chatterbox non installato. Installa in un env di test con: "
            "venv/bin/pip install git+https://github.com/resemble-ai/chatterbox.git"
        ) from exc

    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    refs = {
        "giulia": os.getenv("SPIKE_CHATTERBOX_GIULIA_VOICE", os.getenv("SPIKE_GIULIA_VOICE")),
        "marco": os.getenv("SPIKE_CHATTERBOX_MARCO_VOICE", os.getenv("SPIKE_MARCO_VOICE")),
    }
    segment_paths: list[Path] = []

    for idx, segment in enumerate(segments, start=1):
        kwargs = {"language_id": "it"}
        ref = refs.get(segment.speaker.lower())
        if ref:
            kwargs["audio_prompt_path"] = ref
        wav = model.generate(segment.text, **kwargs)
        segment_path = output_path.with_name(f"{output_path.stem}_seg{idx}.wav")
        ta.save(str(segment_path), wav, model.sr)
        segment_paths.append(segment_path)

    combine_wavs(segment_paths, output_path)
    return "Chatterbox Multilingual: turn stitching locale con language_id=it. Reference voice opzionali via SPIKE_GIULIA_VOICE/SPIKE_MARCO_VOICE."


def run_fish_s2(script_text: str, output_path: Path) -> str:
    fish_dir = os.getenv("FISH_SPEECH_DIR")
    if not fish_dir:
        raise RuntimeError(
            "Fish S2 richiede un checkout locale. Imposta FISH_SPEECH_DIR=/percorso/fish-speech "
            "dopo aver installato fishaudio/fish-speech e scaricato fishaudio/s2-pro."
        )

    fish_path = Path(fish_dir).expanduser().resolve()
    if not fish_path.exists():
        raise RuntimeError(f"FISH_SPEECH_DIR non esiste: {fish_path}")

    transcript = (
        script_text.replace("[SPEAKER: Giulia]", "<|speaker:1|>")
        .replace("[SPEAKER: Marco]", "<|speaker:2|>")
        .replace("[ride]", "[laugh]")
        .replace("[pausa]", "[pause]")
    )
    transcript_path = output_path.with_suffix(".fish_s2.txt")
    transcript_path.write_text(transcript, encoding="utf-8")

    command = os.getenv("FISH_S2_COMMAND")
    if not command:
        raise RuntimeError(
            "Fish S2 non ha un comando CLI stabile nel repo principale per questo spike. "
            "Imposta FISH_S2_COMMAND usando {input} e {output}, per esempio uno script wrapper locale "
            "che chiama fish-speech S2 e scrive il WAV finale."
        )

    rendered = command.format(input=str(transcript_path), output=str(output_path))
    subprocess.run(rendered, cwd=str(fish_path), shell=True, check=True)
    if not output_path.exists():
        raise RuntimeError(f"Fish S2 command completato ma non ha creato {output_path}")
    return "Fish Audio S2: candidato native multi-speaker/multi-turn. Eseguito tramite FISH_S2_COMMAND."


def build_report(results: list[Result], script_text: str, index_path: Path) -> None:
    cards = []
    for result in results:
        if result.output and Path(result.output).exists():
            rel = Path(result.output).name
            player = f'<audio controls preload="metadata" src="{html.escape(rel)}"></audio>'
        else:
            player = "<div class='missing'>Audio non generato</div>"
        seconds = f"{result.seconds:.1f}s" if result.seconds is not None else "-"
        cards.append(
            f"""
            <section class="card {html.escape(result.status)}">
              <div class="row">
                <h2>{html.escape(result.label)}</h2>
                <span>{html.escape(result.status.upper())}</span>
              </div>
              {player}
              <p><strong>Tempo:</strong> {html.escape(seconds)}</p>
              <p>{html.escape(result.notes)}</p>
            </section>
            """
        )

    index_path.write_text(
        f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NewsicaTV TTS Spike</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #10131a; color: #eef2f8; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .intro {{ color: #aab3c2; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .card {{ border: 1px solid #2b3242; border-radius: 8px; padding: 16px; background: #171c26; }}
    .card.ok {{ border-color: #2e7d5b; }}
    .card.error {{ border-color: #8b3a3a; }}
    .row {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    .row span {{ color: #aab3c2; font-size: 12px; letter-spacing: .06em; }}
    audio {{ width: 100%; margin: 12px 0; }}
    pre {{ white-space: pre-wrap; background: #0b0e14; border: 1px solid #2b3242; padding: 14px; border-radius: 8px; color: #d6deea; }}
    .missing {{ padding: 14px; border: 1px dashed #596273; border-radius: 8px; color: #aab3c2; margin: 12px 0; }}
  </style>
</head>
<body>
  <main>
    <h1>NewsicaTV TTS Spike</h1>
    <p class="intro">Confronto locale tra Fish Audio S2, Chatterbox Multilingual e Kyutai Pocket TTS.</p>
    <div class="grid">
      {''.join(cards)}
    </div>
    <h2>Copione usato</h2>
    <pre>{html.escape(script_text)}</pre>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def run_spike(script_text: str, engines: list[str]) -> list[Result]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "spike_script.txt").write_text(script_text, encoding="utf-8")
    segments = parse_script(script_text)
    results: list[Result] = []

    engine_labels = {
        "fish-s2": "Fish Audio S2",
        "chatterbox": "Chatterbox Multilingual",
        "kyutai": "Kyutai Pocket TTS",
    }

    for engine in engines:
        output_path = OUT_DIR / f"{engine}.wav"
        if output_path.exists():
            output_path.unlink()
        start = time.perf_counter()
        try:
            if engine == "fish-s2":
                notes = run_fish_s2(script_text, output_path)
            elif engine == "chatterbox":
                notes = run_chatterbox(segments, output_path)
            elif engine == "kyutai":
                notes = run_kyutai(segments, output_path)
            else:
                raise RuntimeError(f"Engine non supportato: {engine}")
            elapsed = time.perf_counter() - start
            results.append(Result(engine, engine_labels[engine], "ok", str(output_path), elapsed, notes))
        except Exception as exc:
            elapsed = time.perf_counter() - start
            error_path = OUT_DIR / f"{engine}_error_silence.wav"
            write_error_audio(error_path)
            results.append(Result(engine, engine_labels.get(engine, engine), "error", str(error_path), elapsed, str(exc)))

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps([result.__dict__ for result in results], indent=2), encoding="utf-8")
    build_report(results, script_text, OUT_DIR / "index.html")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera una spike comparativa TTS per NewsicaTV.")
    parser.add_argument("--script-file", help="File copione con tag [SPEAKER: Giulia]/[SPEAKER: Marco].")
    parser.add_argument("--text", help="Copione inline. Se omesso usa un copione fisso di test.")
    parser.add_argument(
        "--engines",
        default="fish-s2,chatterbox,kyutai",
        help="Lista separata da virgole: fish-s2,chatterbox,kyutai",
    )
    parser.add_argument("--open", action="store_true", help="Apre la pagina HTML di confronto a fine generazione.")
    args = parser.parse_args()

    if args.script_file:
        script_text = Path(args.script_file).read_text(encoding="utf-8")
    elif args.text:
        script_text = args.text
    else:
        script_text = DEFAULT_SCRIPT

    engines = [item.strip() for item in args.engines.split(",") if item.strip()]
    results = run_spike(script_text, engines)

    print(f"Spike completata in: {OUT_DIR}")
    for result in results:
        print(f"- {result.label}: {result.status} | {result.output}")
        if result.status != "ok":
            print(f"  {result.notes}")
    print(f"Apri: {OUT_DIR / 'index.html'}")

    if args.open:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        if shutil.which(opener):
            subprocess.run([opener, str(OUT_DIR / "index.html")], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
