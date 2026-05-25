from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from newsica.audio.ai_music_runtime import schedule_rotation_fill_job


@dataclass
class PlayoutExecutionContext:
    playout: Any
    state_reader: Callable[[], dict]
    state_updater: Callable[..., None]
    trigger_next_block: Callable[[], None]
    sleep: Callable[[float], None] = time.sleep


class PlayoutEvent(ABC):
    def __init__(self) -> None:
        self.active_idx: int | None = None

    def with_active_idx(self, active_idx: int | None) -> "PlayoutEvent":
        self.active_idx = active_idx
        return self

    @abstractmethod
    def execute(self, context: PlayoutExecutionContext) -> None:
        pass


class TriggerNextBlockEvent(PlayoutEvent):
    def execute(self, context: PlayoutExecutionContext) -> None:
        context.trigger_next_block()


class PlayJingleEvent(PlayoutEvent):
    def __init__(self, file: str, label: str, next_segment: str | None = None):
        super().__init__()
        self.file = file
        self.label = label
        self.next_segment = next_segment

    def execute(self, context: PlayoutExecutionContext) -> None:
        if self.next_segment:
            context.state_updater(current_segment=self.next_segment)
        context.playout.queue_jingle(self.file, self.label)


class PlayVoiceMixEvent(PlayoutEvent):
    def __init__(
        self,
        voice_file: str,
        music_file: str | None,
        character: str,
        title: str,
        segment: str,
        next_segment: str | None = None,
    ):
        super().__init__()
        self.voice_file = voice_file
        self.music_file = music_file
        self.character = character
        self.title = title
        self.segment = segment
        self.next_segment = next_segment

    def execute(self, context: PlayoutExecutionContext) -> None:
        block_info = {
            "status": "ON_AIR",
            "current_block": self.character,
            "current_title": f"{self.title} - {self.segment}",
            "breaking_news_available": False,
        }
        if self.music_file:
            context.playout.mix_and_queue(self.music_file, self.voice_file, block_info)
        else:
            context.playout.queue_pcm_from_file(self.voice_file, block_info)
        if self.next_segment:
            context.state_updater(current_segment=self.next_segment)


class PlayVoiceEvent(PlayoutEvent):
    def __init__(
        self,
        file: str,
        character: str,
        title: str,
        segment: str,
        next_segment: str | None = None,
    ):
        super().__init__()
        self.file = file
        self.character = character
        self.title = title
        self.segment = segment
        self.next_segment = next_segment

    def execute(self, context: PlayoutExecutionContext) -> None:
        block_info = {
            "status": "ON_AIR",
            "current_block": self.character,
            "current_title": f"{self.title} - {self.segment}",
            "breaking_news_available": False,
        }
        context.playout.queue_pcm_from_file(self.file, block_info)
        if self.next_segment:
            context.state_updater(current_segment=self.next_segment)


class PlayMusicEvent(PlayoutEvent):
    def __init__(
        self,
        file: str,
        label: str,
        trigger_ai_music_gen: bool = False,
        theme: str | None = None,
    ):
        super().__init__()
        self.file = file
        self.label = label
        self.trigger_ai_music_gen = trigger_ai_music_gen
        self.theme = theme

    def execute(self, context: PlayoutExecutionContext) -> None:
        context.playout.queue_single_music_track(self.file)
        if self.trigger_ai_music_gen:
            schedule_rotation_fill_job("director", theme=self.theme)


class PlayMusicDeadlineEvent(PlayoutEvent):
    def __init__(self, file: str | None, deadline, label: str):
        super().__init__()
        self.file = file
        self.deadline = deadline
        self.label = label

    def execute(self, context: PlayoutExecutionContext) -> None:
        context.playout.queue_music_track(self.deadline)


class PlaySilenceFallbackEvent(PlayoutEvent):
    def __init__(self, seconds: float):
        super().__init__()
        self.seconds = seconds

    def execute(self, context: PlayoutExecutionContext) -> None:
        context.sleep(self.seconds)
