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
        # Il segmento reale viene corretto più sotto nel caso in cui il blocco
        # non abbia audio pronto e debba cadere direttamente in rotazione musicale.
        jingle_file, jingle_label = get_jingle_for_block(block_type)
        jingle_next_seg = "music_rotation" if block_type == "music_only" else "voice_part_1"
        opening_jingle = PlayJingleEvent(jingle_file, jingle_label, next_segment=jingle_next_seg)
        events.append(opening_jingle)
        
        if block_type == "music_only":
            ready_dir = os.path.join(RUNTIME_DIR, "assets", "ready", scheduled_slot.replace(":", ""))
            voice_file = os.path.join(ready_dir, "audio.wav")
            if os.path.exists(voice_file):
                music_file = self.music_selector(theme)
                events.append(PlayVoiceMixEvent(
                    voice_file=voice_file,
                    music_file=music_file,
                    character=block_type,
                    title=title,
                    segment="intro",
                    next_segment="music_rotation"
                ))
            
            # Per la musica continua, semplicemente aggiungiamo eventi di musica fino alla deadline
            events.append(self._create_music_until_deadline(next_time, theme))
            return events

        # 2. Leggi il manifest per il contenuto testuale dal DB
        ready_dir = os.path.join(RUNTIME_DIR, "assets", "ready", scheduled_slot.replace(":", ""))
        voice_file = os.path.join(ready_dir, "audio.wav")
        
        manifest = {}
        if os.path.exists(voice_file):
            from newsica.storage.repositories.audio_metadata_repository import get_metadata
            try:
                meta_row = get_metadata(voice_file)
                if meta_row and meta_row.get("metadata"):
                    manifest = meta_row["metadata"]
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
            try:
                from newsica.broadcast.runtime_state import get_current_state, write_state_files
                state = get_current_state()
                if state and state.get("status") != "OFFLINE":
                    block_labels = {
                        "news": "Notiziario",
                        "sport": "Rubrica Sportiva",
                        "meteo": "Meteo Update",
                        "wellness": "Rubrica Wellness",
                        "podcast": "Podcast Speciale",
                        "flash_60s": "Flash News",
                    }
                    label = block_labels.get(block_type, block_type.title())
                    state["current_title"] = f"Rotazione Musicale - In attesa di {label}"
                    state["current_segment"] = "music_rotation_until_deadline"
                    write_state_files(state)
            except Exception as e:
                print(f"⚠️ [PlayoutPlanner] Errore aggiornamento stato in fallback: {e}")

            opening_jingle.next_segment = "music_rotation_until_deadline"
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
                        deadline=stacco_deadline_time,
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
        return PlayMusicDeadlineEvent(music_file, deadline, "music_rotation")
