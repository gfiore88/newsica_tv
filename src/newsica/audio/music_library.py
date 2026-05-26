from __future__ import annotations

import json
import os
import random
from collections import deque
from pathlib import Path

from newsica.config.paths import ASSETS_DIR, MUSIC_DIR, RUNTIME_DIR
from newsica.audio.music_mode import MUSIC_MODE_AI_ONLY, read_music_mode

AI_MUSIC_DIR = ASSETS_DIR / "ai_music"
SUPPORTED_AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg")
ROTATION_HISTORY_FILE = RUNTIME_DIR / "music_rotation_history.json"
DEFAULT_RECENT_WINDOW = int(os.getenv("MUSIC_ROTATION_RECENT_WINDOW", "8"))


class MusicLibrary:
    def __init__(self, music_dir=MUSIC_DIR, ai_music_dir=AI_MUSIC_DIR):
        self.music_dir = Path(music_dir)
        self.ai_music_dir = Path(ai_music_dir)
        self._tracks_by_source = {}
        self._last_source = None
        self._recent_tracks = deque(maxlen=max(1, DEFAULT_RECENT_WINDOW))
        self._load_recent_history()

    def refresh(self):
        self._tracks_by_source = {
            "library": self._scan(self.music_dir),
            "ai": self._scan(self.ai_music_dir),
        }

    def _load_recent_history(self):
        if not ROTATION_HISTORY_FILE.exists():
            return
        try:
            payload = json.loads(ROTATION_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        recent_tracks = payload.get("recent_tracks", [])
        if not isinstance(recent_tracks, list):
            return
        self._recent_tracks = deque(
            [str(path) for path in recent_tracks if isinstance(path, str)],
            maxlen=max(1, DEFAULT_RECENT_WINDOW),
        )

    def _save_recent_history(self):
        try:
            ROTATION_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            ROTATION_HISTORY_FILE.write_text(
                json.dumps({"recent_tracks": list(self._recent_tracks)}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _recent_window_for_candidates(self, candidates):
        if len(candidates) <= 1:
            return 0
        return min(len(candidates) - 1, self._recent_tracks.maxlen)

    def _recent_tracks_set(self, candidates):
        recent_window = self._recent_window_for_candidates(candidates)
        if recent_window <= 0:
            return set()
        return set(list(self._recent_tracks)[-recent_window:])

    def _remember_track(self, track):
        if not track:
            return
        self._recent_tracks.append(str(track))
        self._save_recent_history()

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

        source_items = list(self._tracks_by_source.items())
        if mode == MUSIC_MODE_AI_ONLY:
            source_items = [("ai", self._tracks_by_source.get("ai", []))]

        source_candidates = {}
        all_candidates = []
        for source, tracks in source_items:
            candidates = [path for path in tracks if str(path) != exclude]
            if not candidates:
                candidates = list(tracks)
            if not candidates:
                continue

            if source == "ai":
                if theme:
                    normalized_theme = " ".join(theme.lower().strip().split())
                    thematic_candidates = []
                    from newsica.storage.repositories.audio_metadata_repository import get_metadata
                    for path in candidates:
                        meta_row = get_metadata(str(path.resolve()))
                        if meta_row and meta_row.get("metadata"):
                            meta = meta_row["metadata"]
                            track_theme = meta.get("theme")
                            if track_theme:
                                normalized_track_theme = " ".join(str(track_theme).lower().strip().split())
                                if normalized_track_theme == normalized_theme:
                                    thematic_candidates.append(path)
                    if thematic_candidates:
                        candidates = thematic_candidates
                        print(f"🎵 Filtro musica per il tema '{theme}': trovate {len(candidates)} tracce corrispondenti.")
                    else:
                        print(f"⚠️ Nessun brano corrispondente trovato per il tema '{theme}'. Fallback a tutte le tracce AI.")

                candidates_with_metadata = [path for path in candidates if get_metadata(str(path.resolve())) is not None]
                if candidates_with_metadata:
                    candidates = candidates_with_metadata

            source_candidates[source] = candidates
            all_candidates.extend(candidates)

        available_sources = list(source_candidates)
        if not available_sources:
            return None

        recent_tracks = self._recent_tracks_set(all_candidates)
        fresh_source_candidates = {
            source: [path for path in candidates if str(path) not in recent_tracks]
            for source, candidates in source_candidates.items()
        }
        if any(candidates for candidates in fresh_source_candidates.values()):
            source_candidates = {
                source: candidates
                for source, candidates in fresh_source_candidates.items()
                if candidates
            }
            available_sources = list(source_candidates)

        if len(available_sources) > 1 and self._last_source in available_sources:
            preferred_sources = [source for source in available_sources if source != self._last_source]
        else:
            preferred_sources = available_sources

        source = random.choice(preferred_sources)
        candidates = source_candidates[source]
        track = random.choice(candidates)
        self._last_source = source
        self._remember_track(track)
        return str(track)
