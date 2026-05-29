from __future__ import annotations

import json
import os
import random
from collections import deque
from pathlib import Path

from newsica.config.paths import ASSETS_DIR, MUSIC_DIR, RUNTIME_DIR
from newsica.audio.music_mode import MUSIC_MODE_AI_ONLY, read_music_mode
from newsica.storage.repositories.audio_metadata_repository import get_metadata

AI_MUSIC_DIR = RUNTIME_DIR / "assets" / "ai_music"
SUPPORTED_AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg")
ROTATION_HISTORY_FILE = RUNTIME_DIR / "music_rotation_history.json"
ROTATION_BLOCKS_FILE = RUNTIME_DIR / "music_rotation_blocks.json"
DEFAULT_RECENT_WINDOW = int(os.getenv("MUSIC_ROTATION_RECENT_WINDOW", "20"))
DEFAULT_BLOCK_LOG_LIMIT = int(os.getenv("MUSIC_ROTATION_BLOCK_LOG_LIMIT", "20"))
DEFAULT_THEMED_MIN_TRACKS = int(os.getenv("MUSIC_THEME_MIN_TRACKS", "3"))
GENERIC_THEMELESS_MUSIC_TITLE = os.getenv("NEWSICA_GENERIC_MUSIC_TITLE", "Newsica Music Flow")


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
        sanitized_tracks = []
        for path in recent_tracks:
            if not isinstance(path, str):
                continue
            try:
                resolved = Path(path).resolve()
            except Exception:
                continue
            if not resolved.exists():
                continue
            if resolved.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                continue
            sanitized_tracks.append(str(resolved))
        self._recent_tracks = deque(
            sanitized_tracks,
            maxlen=max(1, DEFAULT_RECENT_WINDOW),
        )
        if len(sanitized_tracks) != len(recent_tracks):
            self._save_recent_history()

    def _save_recent_history(self):
        try:
            ROTATION_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            ROTATION_HISTORY_FILE.write_text(
                json.dumps({"recent_tracks": list(self._recent_tracks)}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _append_rotation_block_event(self, event):
        if not event:
            return
        payload = {"events": []}
        try:
            if ROTATION_BLOCKS_FILE.exists():
                payload = json.loads(ROTATION_BLOCKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            payload = {"events": []}

        events = payload.get("events", [])
        if not isinstance(events, list):
            events = []
        events.append(event)
        payload["events"] = events[-max(1, DEFAULT_BLOCK_LOG_LIMIT):]

        try:
            ROTATION_BLOCKS_FILE.parent.mkdir(parents=True, exist_ok=True)
            ROTATION_BLOCKS_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
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
        try:
            normalized = str(Path(track).resolve())
        except Exception:
            normalized = str(track)
        self._recent_tracks.append(normalized)
        self._save_recent_history()

    def remember_track(self, track):
        self._remember_track(track)

    def _scan(self, directory):
        if not directory.exists():
            return []
        return sorted(
            [
                path
                for path in directory.rglob("*")
                if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
            ],
            key=lambda path: str(path).lower(),
        )

    def _has_local_metadata(self, track_path: Path) -> bool:
        if track_path.with_suffix(".meta").exists():
            return True
        return get_metadata(str(track_path.resolve())) is not None

    @staticmethod
    def _normalize_theme(theme: str | None) -> str:
        return " ".join(str(theme or "").lower().strip().split())

    def count_ai_tracks_for_theme(self, theme: str | None) -> int:
        normalized_theme = self._normalize_theme(theme)
        if not normalized_theme:
            return 0

        self.refresh()
        count = 0
        for path in self._tracks_by_source.get("ai", []):
            meta_row = get_metadata(str(path.resolve()))
            if not meta_row or not meta_row.get("metadata"):
                continue
            track_theme = self._normalize_theme(meta_row["metadata"].get("theme"))
            if track_theme == normalized_theme:
                count += 1
        return count

    def has_minimum_theme_catalog(self, theme: str | None, minimum: int | None = None) -> bool:
        minimum = DEFAULT_THEMED_MIN_TRACKS if minimum is None else max(0, int(minimum))
        return self.count_ai_tracks_for_theme(theme) >= minimum

    def get_counts(self):
        self.refresh()
        return {
            source: len(tracks)
            for source, tracks in self._tracks_by_source.items()
        }

    def get_random_track(self, exclude=None, theme=None, remember=True):
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

                candidates_with_metadata = [path for path in candidates if self._has_local_metadata(path)]
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
        blocked_candidates = {
            source: [str(path.resolve()) for path in candidates if str(path) in recent_tracks]
            for source, candidates in source_candidates.items()
        }
        if any(candidates for candidates in fresh_source_candidates.values()):
            blocked_tracks = []
            for blocked in blocked_candidates.values():
                blocked_tracks.extend(blocked)
            if blocked_tracks:
                self._append_rotation_block_event(
                    {
                        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                        "reason": "recent_window",
                        "recent_window": len(recent_tracks),
                        "candidate_count": len(all_candidates),
                        "blocked_tracks": blocked_tracks,
                    }
                )
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
        if remember:
            self._remember_track(track)
        return str(track)
