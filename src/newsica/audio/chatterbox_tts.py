from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_REFS = {
    "giulia": BASE_DIR / "assets" / "voice_refs" / "giulia_reference.wav",
    "marco": BASE_DIR / "assets" / "voice_refs" / "marco_reference.wav",
}


def _speaker_key(speaker: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", speaker).lower()


def _device() -> str:
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def synthesize_segments(segments: list[dict], output_dir: Path) -> list[dict]:
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    output_dir.mkdir(parents=True, exist_ok=True)
    device = _device()
    print(f"Chatterbox: loading multilingual TTS on {device}...")
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)

    outputs = []
    for idx, segment in enumerate(segments, start=1):
        speaker = segment["speaker"]
        text = segment["text"]
        key = _speaker_key(speaker)
        ref_path = Path(segment.get("reference_audio") or DEFAULT_REFS.get(key, DEFAULT_REFS["giulia"]))

        if not ref_path.exists():
            raise FileNotFoundError(f"Reference audio missing for {speaker}: {ref_path}")

        output_path = output_dir / f"podcast_seg_{idx}.wav"
        print(f"Chatterbox: segment {idx}/{len(segments)} | speaker={speaker} | ref={ref_path}")
        wav = model.generate(
            text,
            language_id="it",
            audio_prompt_path=str(ref_path),
        )
        ta.save(str(output_path), wav, model.sr)
        outputs.append(
            {
                "speaker": speaker,
                "path": str(output_path),
                "sample_rate": model.sr,
            }
        )

    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch Chatterbox synthesis for NewsicaTV podcast segments.")
    parser.add_argument("--segments-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest-json", required=True)
    args = parser.parse_args()

    with open(args.segments_json, "r", encoding="utf-8") as f:
        segments = json.load(f)

    outputs = synthesize_segments(segments, Path(args.output_dir))

    with open(args.manifest_json, "w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
