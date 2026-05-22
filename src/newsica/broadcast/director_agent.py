import os
import json
import datetime
import random
import wave
from newsica.config.paths import TMP_DIR, RUNTIME_DIR, ASSETS_DIR
from newsica.utils.audit_logger import log_decision

def get_audio_duration(file_path):
    if not os.path.exists(file_path):
        return 0.0
    try:
        with wave.open(file_path, 'r') as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0
from newsica.broadcast.scheduler import (
    get_current_block_info,
    get_next_block_info_for_key,
    schedule_deadline,
    get_wallclock_schedule_key
)
from newsica.broadcast.runtime_state import get_current_state, write_state_files
from newsica.editorial.memory import (
    add_title,
    add_rubric,
    add_music_track,
    is_title_recent,
    is_music_track_recent,
    should_short_intro,
    update_last_intro
)
from newsica.audio.jingles import get_jingle_for_block, CLASSIC_JINGLE_FILE

EVENING_PODCAST_SLOT = "20:00"
EVENING_PODCAST_TITLE = "Newsica Podcast - Dopo Sera"
EVENING_PODCAST_MIN_REMAINING_SECONDS = 20 * 60

class DirectorAgent:
    def __init__(self, playout=None):
        self.playout = playout
        # Carica percorsi jingle
        self.classic_jingle = str(CLASSIC_JINGLE_FILE)
        
    def decide_next_action(self):
        """
        Analizza lo stato corrente e il palinsesto per determinare l'azione immediata.
        Restituisce un dizionario contenente l'azione e i relativi parametri.
        """
        state = get_current_state()
        status = state.get("status", "OFFLINE")
        current_block = state.get("current_block", "")
        
        # 1. Se siamo in SPECIAL_BROADCAST, gestiamo la copertura speciale
        if status == "SPECIAL_BROADCAST":
            return self._handle_special_broadcast(state)
            
        # 2. Leggiamo il blocco programmato dal palinsesto
        block_type, title, next_title, next_time, current_time, active_idx = get_current_block_info()
        
        # Se lo stato attuale è OFFLINE o non coincide con il blocco corrente, inizializziamo la transizione
        if status == "OFFLINE" or state.get("scheduled_slot") != current_time:
            print(f"🎬 [DirectorAgent] Inizializzazione fascia palinsesto: {current_time} ({title})")
            log_decision("DirectorAgent", f"Inizializzazione fascia palinsesto: {current_time} ({title})", level="PLAYOUT")
            return self._initialize_scheduled_block(block_type, title, next_title, next_time, current_time)
            
        # 3. Gestiamo la progressione interna del blocco attivo
        return self._progress_current_block(state, block_type, title, next_title, next_time, current_time)

    def _initialize_scheduled_block(self, block_type, title, next_title, next_time, current_time):
        """
        Prepara il passaggio a un nuovo blocco di palinsesto.
        """
        self._clear_transient_audio()
        new_state = {
            "status": "ON_AIR",
            "current_block": block_type,
            "current_title": title,
            "current_segment": "init",
            "next_block": next_title,
            "next_start": next_time,
            "scheduled_slot": current_time,
            "breaking_news_available": False,
            "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }
        write_state_files(new_state)
        
        # Ritorna l'azione di play jingle d'apertura rubrica
        jingle_file, jingle_label = get_jingle_for_block(block_type)
        return {
            "action": "PLAY_JINGLE",
            "file": jingle_file,
            "label": jingle_label,
            "next_segment": "intro"
        }

    def _clear_transient_audio(self):
        """
        Invalida gli artefatti audio temporanei quando cambia fascia.
        `tmp/audio.wav` e `tmp/audio_part*.wav` non sono cache globali: appartengono
        allo slot appena generato e non possono essere riusati dal blocco successivo.
        """
        transient_names = {"audio.wav", "is_multipart.txt"}
        for file_name in os.listdir(TMP_DIR):
            if (
                file_name in transient_names
                or (file_name.startswith("audio_part") and file_name.endswith(".wav"))
            ):
                try:
                    os.remove(os.path.join(TMP_DIR, file_name))
                except FileNotFoundError:
                    pass
                except Exception as e:
                    print(f"⚠️ Impossibile rimuovere audio temporaneo {file_name}: {e}")

    def _progress_current_block(self, state, block_type, title, next_title, next_time, current_time):
        """
        Gestisce la progressione interna dei segmenti del blocco attivo.
        """
        current_segment = state.get("current_segment", "init")
        
        if block_type == "music_only":
            return self._handle_music_only_progression(state, next_time)
            
        elif block_type == "podcast":
            return self._handle_podcast_progression(state, title, current_segment, next_time)
            
        else:
            # Rubriche standard: news, sport, meteo, wellness
            return self._handle_standard_rubric_progression(state, block_type, title, current_segment, next_time)

    def _handle_music_only_progression(self, state, next_time):
        """
        Fascia puramente musicale: riproduce brani a ciclo continuo fino alla deadline.
        """
        deadline = schedule_deadline(next_time)
        if datetime.datetime.now() >= deadline:
            return {"action": "TRIGGER_NEXT_BLOCK"}
            
        time_remaining = (deadline - datetime.datetime.now()).total_seconds()
        trigger_ai_music_gen = time_remaining >= 180
        
        # Sceglie un brano musicale rispettando la memoria editoriale
        music_file = self._select_non_repeated_music()
        if music_file:
            add_music_track(music_file)
            return {
                "action": "PLAY_MUSIC",
                "file": music_file,
                "label": "music_rotation",
                "trigger_ai_music_gen": trigger_ai_music_gen
            }
        else:
            return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 5}

    def _handle_standard_rubric_progression(self, state, block_type, title, current_segment, next_time):
        """
        Progressione per news, sport, meteo, wellness.
        """
        scheduled_slot = state.get("scheduled_slot", "").replace(":", "")
        ready_dir = os.path.join(RUNTIME_DIR, "assets", "ready", scheduled_slot)
        
        voice_file = os.path.join(ready_dir, "audio.wav")
        multipart_indicator = os.path.join(ready_dir, "is_multipart.txt")
        manifest_file = os.path.join(ready_dir, "manifest.json")
        if os.path.exists(ready_dir):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                if manifest.get("character") != block_type or manifest.get("title") != title:
                    print(
                        f"⚠️ [DirectorAgent] Asset pronto non coerente per {scheduled_slot}: "
                        f"atteso {block_type}/{title}, trovato {manifest}."
                    )
                    voice_file = ""
                    multipart_indicator = ""
            except Exception:
                print(f"⚠️ [DirectorAgent] Asset pronto senza manifest valido per {scheduled_slot}. Attendo rigenerazione.")
                voice_file = ""
                multipart_indicator = ""
        
        # Determina se il file generato è multi-part o classico singolo
        is_multipart = False
        num_parts = 0
        if os.path.exists(multipart_indicator):
            try:
                with open(multipart_indicator, "r") as f:
                    num_parts = int(f.read().strip())
                is_multipart = num_parts > 0
            except Exception:
                pass

        if current_segment == "intro" or current_segment == "init":
            voice_duration = 15.0
            if is_multipart and num_parts > 0:
                for i in range(1, num_parts + 1):
                    voice_duration += get_audio_duration(os.path.join(ready_dir, f"audio_part{i}.wav"))
            else:
                voice_duration += get_audio_duration(voice_file)
                
            deadline = schedule_deadline(next_time)
            slot_duration = (deadline - datetime.datetime.now()).total_seconds()
            music_total_time = max(0.0, slot_duration - voice_duration)
            num_music_blocks = num_parts if is_multipart else 1
            state["break_target_duration"] = music_total_time / num_music_blocks
            write_state_files(state)

            # Passiamo alla messa in onda del copione (singolo o multipart)
            if is_multipart and num_parts > 0:
                # Iniziamo la prima parte del multi-part
                next_part_file = os.path.join(ready_dir, "audio_part1.wav")
                if os.path.exists(next_part_file):
                    music_file = self._select_non_repeated_music()
                    if music_file:
                        add_music_track(music_file)
                    state["current_segment"] = "voice_part_1"
                    write_state_files(state)
                    return {
                        "action": "PLAY_VOICE_MIX",
                        "voice_file": next_part_file,
                        "music_file": music_file,
                        "character": block_type,
                        "title": title,
                        "segment": "Parte 1"
                    }
            
            # Flusso classico a parte singola
            if os.path.exists(voice_file):
                music_file = self._select_non_repeated_music()
                if music_file:
                    add_music_track(music_file)
                state["current_segment"] = "meteo_brief_playing" if block_type == "meteo" else "voice_single"
                write_state_files(state)
                return {
                    "action": "PLAY_VOICE_MIX",
                    "voice_file": voice_file,
                    "music_file": music_file,
                    "character": block_type,
                    "title": title,
                    "segment": "Completo"
                }
            
            # Se l'audio non è pronto, inneschiamo un fallback musicale.
            # Questo evita il blocco stream e fa da "attesa".
            state["current_segment"] = "music_rotation_until_deadline"
            write_state_files(state)
            
            music_file = self._select_non_repeated_music()
            if music_file:
                add_music_track(music_file)
                return {
                    "action": "PLAY_MUSIC",
                    "file": music_file,
                    "label": "fallback_non_pronto",
                    "trigger_ai_music_gen": False
                }
            return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}

        elif current_segment == "meteo_brief_playing":
            state["current_segment"] = "music_rotation_until_deadline"
            write_state_files(state)
            return {
                "action": "PLAY_JINGLE",
                "file": self.classic_jingle,
                "label": "stacco_uscita_meteo",
                "next_segment": "music_rotation_until_deadline"
            }

        elif current_segment == "evening_podcast_generate":
            return {
                "action": "WAIT_OR_GENERATE",
                "character": "podcast",
                "title": EVENING_PODCAST_TITLE,
                "time_key": state.get("scheduled_slot"),
                "next_segment": "evening_podcast_ready"
            }

        elif current_segment == "evening_podcast_ready":
            if os.path.exists(voice_file):
                state["current_segment"] = "evening_podcast_playing"
                state["evening_podcast_inserted"] = True
                write_state_files(state)
                return {
                    "action": "PLAY_VOICE",
                    "file": voice_file,
                    "character": "podcast",
                    "title": EVENING_PODCAST_TITLE,
                    "segment": "Extra"
                }
            return {
                "action": "WAIT_OR_GENERATE",
                "character": "podcast",
                "title": EVENING_PODCAST_TITLE,
                "time_key": state.get("scheduled_slot"),
                "next_segment": "evening_podcast_ready"
            }

        elif current_segment == "evening_podcast_playing":
            state["current_segment"] = "voice_closing"
            state["current_block"] = block_type
            state["current_title"] = title
            write_state_files(state)
            return {
                "action": "PLAY_JINGLE",
                "file": self.classic_jingle,
                "label": "stacco_uscita_podcast_serale",
                "next_segment": "music_rotation_until_deadline"
            }

        elif current_segment.startswith("voice_part_"):
            # Gestione del sequenziamento multi-part delle rubriche
            try:
                current_part_idx = int(current_segment.split("_")[-1])
            except ValueError:
                current_part_idx = 1
                
            if current_part_idx < num_parts:
                next_part_idx = current_part_idx + 1
                next_part_file = os.path.join(ready_dir, f"audio_part{next_part_idx}.wav")
                
                # Prima di mandare in onda la prossima parte, riproduciamo 1 o più brani intermedi di stacco
                # Per non saltare il sequenziamento, creiamo uno stato intermedio di stacco musicale
                state["current_segment"] = f"music_stacco_{current_part_idx}_to_{next_part_idx}"
                break_duration = state.get("break_target_duration", 180.0)
                state["stacco_deadline"] = (datetime.datetime.now() + datetime.timedelta(seconds=break_duration)).isoformat()
                write_state_files(state)
                
                music_file = self._select_non_repeated_music()
                if music_file:
                    add_music_track(music_file)
                    return {
                        "action": "PLAY_MUSIC_DEADLINE",
                        "file": music_file,
                        "deadline": state["stacco_deadline"],
                        "label": "stacco_musicale_rubrica"
                    }
            
            # Finito il multi-part, passiamo alla chiusura
            state["current_segment"] = "voice_closing"
            write_state_files(state)
            return {
                "action": "PLAY_JINGLE",
                "file": self.classic_jingle,
                "label": "stacco_uscita",
                "next_segment": "music_rotation_until_deadline"
            }

        elif current_segment.startswith("music_stacco_"):
            # Controllo se il tempo di stacco è terminato
            stacco_deadline_str = state.get("stacco_deadline")
            if stacco_deadline_str:
                stacco_deadline = datetime.datetime.fromisoformat(stacco_deadline_str)
                if datetime.datetime.now() < stacco_deadline:
                    # Riempiamo ancora di musica
                    music_file = self._select_non_repeated_music()
                    if music_file:
                        add_music_track(music_file)
                        return {
                            "action": "PLAY_MUSIC_DEADLINE",
                            "file": music_file,
                            "deadline": stacco_deadline_str,
                            "label": "stacco_musicale_rubrica"
                        }
                    return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}

            # Rientriamo dallo stacco musicale alla parte successiva del parlato
            parts = current_segment.split("_")
            next_part_idx = int(parts[-1])
            scheduled_slot = state.get("scheduled_slot", "").replace(":", "")
            ready_dir = os.path.join(RUNTIME_DIR, "assets", "ready", scheduled_slot)
            next_part_file = os.path.join(ready_dir, f"audio_part{next_part_idx}.wav")
            
            if os.path.exists(next_part_file):
                music_file = self._select_non_repeated_music()
                if music_file:
                    add_music_track(music_file)
                state["current_segment"] = f"voice_part_{next_part_idx}"
                write_state_files(state)
                return {
                    "action": "PLAY_VOICE_MIX",
                    "voice_file": next_part_file,
                    "music_file": music_file,
                    "character": block_type,
                    "title": title,
                    "segment": f"Parte {next_part_idx}"
                }
            else:
                # Fallback se la parte non esiste
                state["current_segment"] = "voice_closing"
                write_state_files(state)
                return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}

        elif current_segment == "voice_single":
            # Fine blocco parlato a singola parte -> manda sigla di chiusura
            state["current_segment"] = "voice_closing"
            write_state_files(state)
            return {
                "action": "PLAY_JINGLE",
                "file": self.classic_jingle,
                "label": "stacco_uscita",
                "next_segment": "music_rotation_until_deadline"
            }

        elif current_segment == "voice_closing" or current_segment == "music_rotation_until_deadline":
            # Una volta completato il blocco parlato della rubrica, trasmette musica fino al cambio fascia oraria
            if self._should_insert_evening_podcast(state, block_type, current_time=state.get("scheduled_slot"), next_time=next_time):
                state["current_segment"] = "evening_podcast_generate"
                state["evening_podcast_inserted"] = True
                write_state_files(state)
                jingle_file, jingle_label = get_jingle_for_block("podcast")
                return {
                    "action": "PLAY_JINGLE",
                    "file": jingle_file,
                    "label": jingle_label,
                    "next_segment": "evening_podcast_generate"
                }

            state["current_segment"] = "music_rotation_until_deadline"
            write_state_files(state)
            
            deadline = schedule_deadline(next_time)
            if datetime.datetime.now() >= deadline:
                return {"action": "TRIGGER_NEXT_BLOCK"}
                
            time_remaining = (deadline - datetime.datetime.now()).total_seconds()
            trigger_ai_music_gen = time_remaining >= 180
                
            music_file = self._select_non_repeated_music()
            if music_file:
                add_music_track(music_file)
                return {
                    "action": "PLAY_MUSIC",
                    "file": music_file,
                    "label": "music_rotation",
                    "trigger_ai_music_gen": trigger_ai_music_gen
                }
            else:
                return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 5}
                
        return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}

    def _should_insert_evening_podcast(self, state, block_type, current_time, next_time):
        if block_type != "news":
            return False
        if current_time != EVENING_PODCAST_SLOT:
            return False
        if state.get("evening_podcast_inserted"):
            return False

        deadline = schedule_deadline(next_time)
        time_remaining = (deadline - datetime.datetime.now()).total_seconds()
        return time_remaining >= EVENING_PODCAST_MIN_REMAINING_SECONDS

    def _handle_podcast_progression(self, state, title, current_segment, next_time):
        """
        Gestione specifica per la rubrica Podcast a due voci.
        La pipeline podcast corrente produce un file unico `audio.wav`.
        """
        scheduled_slot = state.get("scheduled_slot", "").replace(":", "")
        ready_dir = os.path.join(RUNTIME_DIR, "assets", "ready", scheduled_slot)
        voice_file = os.path.join(ready_dir, "audio.wav")
        manifest_file = os.path.join(ready_dir, "manifest.json")
        has_valid_audio = os.path.exists(voice_file)

        if os.path.exists(ready_dir):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                if manifest.get("character") != "podcast" or manifest.get("title") != title:
                    print(
                        f"⚠️ [DirectorAgent] Podcast pronto non coerente per {scheduled_slot}: "
                        f"atteso podcast/{title}, trovato {manifest}."
                    )
                    has_valid_audio = False
            except Exception:
                print(f"⚠️ [DirectorAgent] Podcast pronto senza manifest valido per {scheduled_slot}. Attendo rigenerazione.")
                has_valid_audio = False
        
        if current_segment in {"intro", "init", "music_rotation_until_deadline"}:
            if has_valid_audio and not state.get("podcast_played"):
                state["current_segment"] = "podcast_playing"
                state["podcast_played"] = True
                write_state_files(state)
                return {
                    "action": "PLAY_VOICE",
                    "file": voice_file,
                    "character": "podcast",
                    "title": title,
                    "segment": "Completo"
                }
            # Se l'audio non è pronto, inneschiamo un fallback musicale.
            print(f"⚠️ [DirectorAgent] Podcast non pronto per slot {scheduled_slot}. Uso musica finché l'asset non arriva.")
            state["current_segment"] = "music_rotation_until_deadline"
            write_state_files(state)
            
            music_file = self._select_non_repeated_music()
            if music_file:
                add_music_track(music_file)
                return {
                    "action": "PLAY_MUSIC",
                    "file": music_file,
                    "label": "fallback_non_pronto",
                    "trigger_ai_music_gen": False
                }
            return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}

        elif current_segment == "podcast_playing":
            state["current_segment"] = "podcast_closing"
            write_state_files(state)
            return {
                "action": "PLAY_JINGLE",
                "file": self.classic_jingle,
                "label": "stacco_uscita_podcast",
                "next_segment": "music_rotation_until_deadline"
            }
                
        elif current_segment == "podcast_closing" or current_segment == "music_rotation_until_deadline":
            state["current_segment"] = "music_rotation_until_deadline"
            write_state_files(state)
            
            deadline = schedule_deadline(next_time)
            if datetime.datetime.now() >= deadline:
                return {"action": "TRIGGER_NEXT_BLOCK"}
                
            time_remaining = (deadline - datetime.datetime.now()).total_seconds()
            trigger_ai_music_gen = time_remaining >= 180
                
            music_file = self._select_non_repeated_music()
            if music_file:
                add_music_track(music_file)
                return {
                    "action": "PLAY_MUSIC",
                    "file": music_file,
                    "label": "music_rotation",
                    "trigger_ai_music_gen": trigger_ai_music_gen
                }
            else:
                return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 5}
                
        return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}

    def _handle_special_broadcast(self, state):
        """
        Copertura speciale (Edizione Straordinaria).
        Riproduce ripetutamente bollettini di aggiornamento intervallati da musica tesa o stacchi.
        """
        current_segment = state.get("current_segment", "init")
        bn_file = os.path.join(TMP_DIR, "breaking_news.wav")
        
        # Sottofondo sonoro dedicato alle emergenze
        special_theme = os.path.join(ASSETS_DIR, "music", "special_broadcast_theme.mp3")
        if not os.path.exists(special_theme):
            # Fallback se il tema speciale non è presente
            special_theme = self._select_non_repeated_music()
            
        if current_segment == "init" or current_segment == "intro":
            if os.path.exists(bn_file):
                state["current_segment"] = "broadcast_body"
                write_state_files(state)
                return {
                    "action": "PLAY_VOICE_MIX",
                    "voice_file": bn_file,
                    "music_file": special_theme,
                    "character": "breaking_news",
                    "title": "EDIZIONE STRAORDINARIA",
                    "segment": "Bollettino Speciale"
                }
            else:
                return {"action": "WAIT_OR_GENERATE", "character": "breaking_news", "title": "EDIZIONE STRAORDINARIA", "time_key": "SPECIAL"}
                
        elif current_segment == "broadcast_body":
            # Finito il bollettino, se non c'è una revoca manuale o se non sono passati abbastanza minuti,
            # riproduciamo musica di attesa o un altro jingle e poi ripetiamo il ciclo
            state["current_segment"] = "broadcast_waiting"
            write_state_files(state)
            
            # Sfondi tesi di attesa
            return {
                "action": "PLAY_MUSIC",
                "file": special_theme,
                "label": "attesa_edizione_straordinaria"
            }
            
        elif current_segment == "broadcast_waiting":
            # Ripete il bollettino speciale aggiornato
            state["current_segment"] = "intro"
            write_state_files(state)
            return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 5}
            
        return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}

    def notify_interrupt(self, reason, severity_score=0):
        """
        Forza un'interruzione di regia per gestire una breaking news o un'edizione straordinaria.
        """
        state = get_current_state()
        
        if severity_score >= 90:
            print(f"🚨 [DirectorAgent] RILEVATO EVENTO ECCEZIONALE (Score {severity_score}). Attivo SPECIAL_BROADCAST!")
            log_decision("DirectorAgent", f"RILEVATO EVENTO ECCEZIONALE (Score {severity_score}). Attivo SPECIAL_BROADCAST!", level="BREAKING")
            
            # Salviamo lo slot interrotto per decidere come ripristinarlo successivamente
            prev_block = state.get("current_block", "music_only")
            prev_title = state.get("current_title", "")
            prev_slot = state.get("scheduled_slot", "")
            
            special_state = {
                "status": "SPECIAL_BROADCAST",
                "current_block": "trasmissione_straordinaria",
                "current_title": "EDIZIONE STRAORDINARIA",
                "current_segment": "intro",
                "interrupted_block": prev_block,
                "interrupted_title": prev_title,
                "interrupted_slot": prev_slot,
                "interrupted_at": datetime.datetime.now().isoformat(),
                "severity_score": severity_score,
                "reason": reason,
                "next_block": "Ripresa Palinsesto",
                "next_start": "",
                "breaking_news_available": False,
                "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            }
            write_state_files(special_state)
            
            # Jingle breaking news o straordinario se presente
            jingle_file = os.path.join(ASSETS_DIR, "jingles", "jingle_breaking_news.mp3")
            if not os.path.exists(jingle_file):
                jingle_file = self.classic_jingle
                
            return {
                "action": "PLAY_JINGLE",
                "file": jingle_file,
                "label": "jingle_straordinaria",
                "next_segment": "intro"
            }
        else:
            print(f"📢 [DirectorAgent] Rilevata Breaking News ordinaria (Score {severity_score}).")
            return None

    def handle_restore_after_interrupt(self):
        """
        Ripristina il palinsesto ordinario seguendo la regola del 40% di durata residua.
        """
        state = get_current_state()
        status = state.get("status", "OFFLINE")
        
        if status != "SPECIAL_BROADCAST":
            return
            
        interrupted_slot = state.get("interrupted_slot")
        interrupted_block = state.get("interrupted_block", "music_only")
        interrupted_title = state.get("interrupted_title", "")
        
        if not interrupted_slot:
            # Ripristino di base sul wallclock
            write_state_files({"status": "OFFLINE"})
            return
            
        # Calcola la durata residua dello slot interrotto
        try:
            _, _, _, next_time, current_time, _ = get_current_block_info()
            
            if current_time == interrupted_slot:
                deadline = schedule_deadline(next_time)
                now = datetime.datetime.now()
                time_remaining = (deadline - now).total_seconds()
                
                # Calcola la durata reale dello slot dal palinsesto invece di usare
                # un valore fisso di 1800s che era errato per fasce lunghe (es. 2 ore).
                # Usiamo il tempo trascorso dall'inizio slot + il residuo come proxy.
                try:
                    slot_start_hour, slot_start_min = map(int, interrupted_slot.split(":"))
                    slot_start = now.replace(
                        hour=slot_start_hour, minute=slot_start_min,
                        second=0, microsecond=0
                    )
                    if slot_start > now:  # slot del giorno precedente
                        slot_start -= datetime.timedelta(days=1)
                    total_duration = (deadline - slot_start).total_seconds()
                except Exception:
                    total_duration = 1800.0
                
                # Soglia: ripristina se rimangono almeno 5 minuti O almeno il 20% dello slot
                # (soglia abbassata dal 40% originale per evitare restart da parte 1 a fine fascia)
                min_threshold = max(300.0, total_duration * 0.20)
                
                if time_remaining >= min_threshold:
                    print(f"🔄 [DirectorAgent] Ripristino slot interrotto '{interrupted_title}' "
                          f"(Fascia delle {interrupted_slot}) - Rimangono {time_remaining/60:.1f} min "
                          f"su {total_duration/60:.0f} min totali.")
                    log_decision("DirectorAgent", f"Ripristino slot interrotto '{interrupted_title}' (residuo {time_remaining/60:.1f} min).", level="RESTORE")
                    restored_state = {
                        "status": "ON_AIR",
                        "current_block": interrupted_block,
                        "current_title": interrupted_title,
                        "current_segment": "music_rotation_until_deadline",
                        "next_block": state.get("next_block", ""),
                        "next_start": state.get("next_start", ""),
                        "scheduled_slot": interrupted_slot,
                        "breaking_news_available": False,
                        "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    }
                    write_state_files(restored_state)
                    log_decision("DirectorAgent", f"Ripristinato il blocco: {interrupted_title}", level="INIT")
                    return
                else:
                    print(f"⏭️ [DirectorAgent] Slot quasi scaduto ({time_remaining/60:.1f} min residui, "
                          f"soglia {min_threshold/60:.1f} min). Attendo naturale cambio fascia.")
                    log_decision("DirectorAgent", f"Salto ripristino '{interrupted_title}'. Tempo residuo troppo basso ({time_remaining/60:.1f} min).", level="RESTORE")
                    # Non impostiamo OFFLINE: aspettiamo che il watchdog wallclock
                    # rilevi il cambio di fascia naturalmente alla prossima ora
                    restored_state = {
                        "status": "ON_AIR",
                        "current_block": interrupted_block,
                        "current_title": interrupted_title,
                        "current_segment": "music_rotation_until_deadline",
                        "next_block": state.get("next_block", ""),
                        "next_start": state.get("next_start", ""),
                        "scheduled_slot": interrupted_slot,
                        "breaking_news_available": False,
                        "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    }
                    write_state_files(restored_state)
                    return
        except Exception as e:
            print(f"⚠️ Errore durante il calcolo del ripristino: {e}")
            
        # Altrimenti passiamo direttamente al blocco successivo previsto dal palinsesto
        print("⏭️ [DirectorAgent] Lo slot interrotto è quasi scaduto (<40% residuo). Salto direttamente alla programmazione successiva.")
        write_state_files({"status": "OFFLINE"})

    def _select_non_repeated_music(self):
        """
        Seleziona un brano musicale randomico che non è presente nella memoria recente.
        """
        if not self.playout:
            # Fallback se playout non è agganciato
            return None
            
        # Prova fino a 10 volte per trovare un brano non riprodotto di recente
        for _ in range(10):
            music_file = self.playout.get_random_music()
            if not music_file:
                break
            if not is_music_track_recent(music_file):
                return music_file
                
        # Se tutti i brani sono recenti, ne restituisce uno a caso per non interrompere l'audio
        return self.playout.get_random_music()
