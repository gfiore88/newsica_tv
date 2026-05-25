from abc import ABC, abstractmethod

class PlayoutEvent(ABC):
    @abstractmethod
    def execute(self, playout, state_updater):
        """
        Esegue l'evento audio tramite l'oggetto playout e aggiorna lo stato
        usando lo state_updater.
        """
        pass

class PlayJingleEvent(PlayoutEvent):
    def __init__(self, file, label, next_segment):
        self.file = file
        self.label = label
        self.next_segment = next_segment

    def execute(self, playout, state_updater):
        playout.queue_jingle(self.file, self.label)
        state_updater(current_segment=self.next_segment)

class PlayVoiceMixEvent(PlayoutEvent):
    def __init__(self, voice_file, music_file, character, title, segment, next_segment):
        self.voice_file = voice_file
        self.music_file = music_file
        self.character = character
        self.title = title
        self.segment = segment
        self.next_segment = next_segment

    def execute(self, playout, state_updater):
        block_info = {
            "status": "ON_AIR",
            "current_block": self.character,
            "current_title": f"{self.title} - {self.segment}",
            "breaking_news_available": False
        }
        if self.music_file:
            playout.mix_and_queue(self.music_file, self.voice_file, block_info)
        else:
            playout.queue_pcm_from_file(self.voice_file, block_info)
        
        state_updater(current_segment=self.next_segment)

class PlayVoiceEvent(PlayoutEvent):
    def __init__(self, file, character, title, segment, next_segment):
        self.file = file
        self.character = character
        self.title = title
        self.segment = segment
        self.next_segment = next_segment

    def execute(self, playout, state_updater):
        block_info = {
            "status": "ON_AIR",
            "current_block": self.character,
            "current_title": f"{self.title} - {self.segment}",
            "breaking_news_available": False
        }
        playout.queue_pcm_from_file(self.file, block_info)
        state_updater(current_segment=self.next_segment)

class PlayMusicEvent(PlayoutEvent):
    def __init__(self, file, label, trigger_ai_music_gen=False):
        self.file = file
        self.label = label
        self.trigger_ai_music_gen = trigger_ai_music_gen

    def execute(self, playout, state_updater):
        playout.queue_single_music_track(self.file)
        if self.trigger_ai_music_gen:
            # L'innesco del worker AI sarà gestito a un livello superiore o tramite callback
            pass

class PlayMusicDeadlineEvent(PlayoutEvent):
    def __init__(self, file, deadline, label):
        self.file = file
        self.deadline = deadline
        self.label = label

    def execute(self, playout, state_updater):
        playout.queue_music_track(self.deadline)

class PlaySilenceFallbackEvent(PlayoutEvent):
    def __init__(self, seconds):
        self.seconds = seconds

    def execute(self, playout, state_updater):
        import time
        time.sleep(self.seconds)
