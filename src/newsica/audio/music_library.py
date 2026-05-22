from __future__ import annotations

import random
from pathlib import Path

from newsica.config.paths import ASSETS_DIR, MUSIC_DIR
from newsica.audio.music_mode import MUSIC_MODE_AI_ONLY, read_music_mode

AI_MUSIC_DIR = ASSETS_DIR / "ai_music"
SUPPORTED_AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg")


class MusicLibrary:
    def __init__(self, music_dir=MUSIC_DIR, ai_music_dir=AI_MUSIC_DIR):
        self.music_dir = Path(music_dir)
        self.ai_music_dir = Path(ai_music_dir)
        self._tracks_by_source = {}
        self._last_source = None

    def refresh(self):
        self._tracks_by_source = {
            "library": self._scan(self.music_dir),
            "ai": self._scan(self.ai_music_dir),
        }

    def _scan(self, directory):
        if not directory.exists():
            return []
        return [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
        ]

    def get_counts(self):
        self.refresh()
        return {
            source: len(tracks)
            for source, tracks in self._tracks_by_source.items()
        }

    def get_random_track(self, exclude=None, theme=None):
        self.refresh()

        mode = read_music_mode()
        if theme:
            mode = MUSIC_MODE_AI_ONLY

        source_items = self._tracks_by_source.items()
        if mode == MUSIC_MODE_AI_ONLY:
            source_items = [("ai", self._tracks_by_source.get("ai", []))]

        available_sources = [
            source
            for source, tracks in source_items
            if any(str(path) != exclude for path in tracks)
        ]
        if not available_sources:
            return None

        if len(available_sources) > 1 and self._last_source in available_sources:
            preferred_sources = [source for source in available_sources if source != self._last_source]
        else:
            preferred_sources = available_sources

        source = random.choice(preferred_sources)
        candidates = [path for path in self._tracks_by_source[source] if str(path) != exclude]
        if not candidates:
            candidates = self._tracks_by_source[source]

        if source == "ai":
            if theme:
                normalized_theme = " ".join(theme.lower().strip().split())
                thematic_candidates = []
                for path in candidates:
                    metadata_file = path.with_suffix(".json")
                    if metadata_file.exists():
                        try:
                            import json
                            with open(metadata_file, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                            track_theme = meta.get("theme")
                            if track_theme:
                                normalized_track_theme = " ".join(str(track_theme).lower().strip().split())
                                if normalized_track_theme == normalized_theme:
                                    thematic_candidates.append(path)
                        except Exception:
                            pass
                if thematic_candidates:
                    candidates = thematic_candidates
                    print(f"🎵 Filtro musica per il tema '{theme}': trovate {len(candidates)} tracce corrispondenti.")
                else:
                    print(f"⚠️ Nessun brano corrispondente trovato per il tema '{theme}'. Fallback a tutte le tracce AI.")

            candidates_with_metadata = [path for path in candidates if path.with_suffix(".json").exists()]
            if candidates_with_metadata:
                candidates = candidates_with_metadata

        track = random.choice(candidates)
        self._last_source = source
        return str(track)
