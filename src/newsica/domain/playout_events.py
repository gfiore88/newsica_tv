from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from newsica.audio.ai_music_runtime import schedule_rotation_fill_job
from newsica.storage.repositories import broadcast_history_repository
from newsica.storage.repositories import asset_slots_repository



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
        
        slot = context.state_reader().get("scheduled_slot", "")
        broadcast_history_repository.add(
            slot_time=slot, block_type="jingle", title=self.label, 
            segment=self.next_segment or "jingle", event_type="PlayJingleEvent", asset_path=self.file
        )
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
        
        slot = context.state_reader().get("scheduled_slot", "")
        broadcast_history_repository.add(
            slot_time=slot, block_type=self.character, title=self.title, 
            segment=self.segment, event_type="PlayVoiceMixEvent", asset_path=self.voice_file
        )
        asset_slots_repository.update_status(slot_time=slot, character=self.character, status="played")
        
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
        
        slot = context.state_reader().get("scheduled_slot", "")
        broadcast_history_repository.add(
            slot_time=slot, block_type=self.character, title=self.title, 
            segment=self.segment, event_type="PlayVoiceEvent", asset_path=self.file
        )
        asset_slots_repository.update_status(slot_time=slot, character=self.character, status="played")
        
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
        slot = context.state_reader().get("scheduled_slot", "")
        context.playout.queue_single_music_track(
            self.file,
            history_slot=slot,
            history_label=self.label,
            history_event_type="PlayMusicEvent",
            history_segment="rotation",
        )
        if self.trigger_ai_music_gen:
            schedule_rotation_fill_job("director", theme=self.theme)


class PlayMusicDeadlineEvent(PlayoutEvent):
    def __init__(self, file: str | None, deadline, label: str):
        super().__init__()
        self.file = file
        self.deadline = deadline
        self.label = label

    def execute(self, context: PlayoutExecutionContext) -> None:
        slot = context.state_reader().get("scheduled_slot", "")
        context.playout.queue_music_track(
            self.deadline,
            preferred_music_file=self.file,
            history_slot=slot,
            history_label=self.label,
            history_event_type="PlayMusicDeadlineEvent",
            history_segment="rotation_deadline",
        )


class PlaySilenceFallbackEvent(PlayoutEvent):
    def __init__(self, seconds: float):
        super().__init__()
        self.seconds = seconds

    def execute(self, context: PlayoutExecutionContext) -> None:
        context.sleep(self.seconds)
