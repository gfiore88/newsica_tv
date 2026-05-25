import os
import json
import datetime
from newsica.config.paths import RUNTIME_DIR
from newsica.domain.playout_events import (
    PlayJingleEvent,
    PlayVoiceMixEvent,
    PlayVoiceEvent,
    PlayMusicEvent,
    PlayMusicDeadlineEvent,
    PlaySilenceFallbackEvent
)
from newsica.audio.jingles import get_jingle_for_block, CLASSIC_JINGLE_FILE
from newsica.broadcast.scheduler import schedule_deadline

class PlayoutPlanner:
    def __init__(self, music_selector):
        self.music_selector = music_selector
        self.classic_jingle = str(CLASSIC_JINGLE_FILE)

    def plan_block(self, block_type, title, next_time, scheduled_slot, theme=None):
        """
        Analizza il palinsesto e il manifest corrente per generare una sequenza di eventi.
        """
        events = []
        
        # 1. Jingle d'apertura
        jingle_file, jingle_label = get_jingle_for_block(block_type)
        events.append(PlayJingleEvent(jingle_file, jingle_label, next_segment="voice_part_1"))
        
        if block_type == "music_only":
            # Per la musica continua, semplicemente aggiungiamo eventi di musica fino alla deadline
            events.append(self._create_music_until_deadline(next_time, theme))
            return events

        # 2. Leggi il manifest per il contenuto testuale
        ready_dir = os.path.join(RUNTIME_DIR, "assets", "ready", scheduled_slot.replace(":", ""))
        manifest_file = os.path.join(ready_dir, "manifest.json")
        
        manifest = {}
        if os.path.exists(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                pass
                
        # Conta le parti audio
        audio_parts = []
        if os.path.exists(ready_dir):
            for i in range(1, 10):
                part_file = os.path.join(ready_dir, f"audio_part{i}.wav")
                if os.path.exists(part_file):
                    audio_parts.append(part_file)
                else:
                    break
        
        single_voice = os.path.join(ready_dir, "audio.wav")
        if not audio_parts and os.path.exists(single_voice):
            audio_parts = [single_voice]

        if not audio_parts:
            # Fallback se non c'è audio
            events.append(PlaySilenceFallbackEvent(2))
            music_file = self.music_selector(theme)
            if music_file:
                events.append(PlayMusicEvent(music_file, "fallback_non_pronto"))
            events.append(self._create_music_until_deadline(next_time, theme))
            return events

        # Calcola le durate e gli stacchi
        deadline = schedule_deadline(next_time)
        slot_duration = (deadline - datetime.datetime.now()).total_seconds()
        # Stima del parlato (possiamo usare 15s come default se non calcoliamo l'header wav)
        music_total_time = max(0.0, slot_duration - (len(audio_parts) * 20)) 
        break_duration = music_total_time / len(audio_parts)

        # 3. Genera la sequenza parlata + stacchi
        for idx, part_file in enumerate(audio_parts):
            music_file = self.music_selector(theme)
            segment_label = f"Parte {idx+1}" if len(audio_parts) > 1 else "Completo"
            next_seg = f"voice_part_{idx+2}" if idx < len(audio_parts) - 1 else "voice_closing"
            
            events.append(PlayVoiceMixEvent(
                voice_file=part_file,
                music_file=music_file,
                character=block_type,
                title=title,
                segment=segment_label,
                next_segment=next_seg
            ))
            
            if idx < len(audio_parts) - 1:
                stacco_deadline_time = datetime.datetime.now() + datetime.timedelta(seconds=break_duration)
                stacco_music = self.music_selector(theme)
                if stacco_music:
                    events.append(PlayMusicDeadlineEvent(
                        file=stacco_music,
                        deadline=stacco_deadline_time.isoformat(),
                        label="stacco_musicale_rubrica"
                    ))

        # 4. Jingle di chiusura e rotazione musicale fino a fine fascia
        events.append(PlayJingleEvent(self.classic_jingle, "stacco_uscita", next_segment="music_rotation_until_deadline"))
        events.append(self._create_music_until_deadline(next_time, theme))

        return events

    def _create_music_until_deadline(self, next_time, theme):
        deadline = schedule_deadline(next_time)
        music_file = self.music_selector(theme)
        # Evento fittizio: potremmo aver bisogno di un evento speciale che cicla la musica
        # o delegare al generatore di richiedere nuovi brani.
        # Creiamo un evento che verrà consumato per riempire il tempo
        return PlayMusicDeadlineEvent(music_file, deadline.isoformat(), "music_rotation")
