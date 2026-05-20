import os
import json
import datetime
import random
from newsica.config.paths import TMP_DIR, RUNTIME_DIR, ASSETS_DIR
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
            return self._initialize_scheduled_block(block_type, title, next_title, next_time, current_time)
            
        # 3. Gestiamo la progressione interna del blocco attivo
        return self._progress_current_block(state, block_type, title, next_title, next_time, current_time)

    def _initialize_scheduled_block(self, block_type, title, next_title, next_time, current_time):
        """
        Prepara il passaggio a un nuovo blocco di palinsesto.
        """
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
            
        # Sceglie un brano musicale rispettando la memoria editoriale
        music_file = self._select_non_repeated_music()
        if music_file:
            add_music_track(music_file)
            return {
                "action": "PLAY_MUSIC",
                "file": music_file,
                "label": "music_rotation"
            }
        else:
            return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 5}

    def _handle_standard_rubric_progression(self, state, block_type, title, current_segment, next_time):
        """
        Progressione per news, sport, meteo, wellness.
        """
        voice_file = os.path.join(TMP_DIR, "audio.wav")
        multipart_indicator = os.path.join(TMP_DIR, "is_multipart.txt")
        
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
            # Passiamo alla messa in onda del copione (singolo o multipart)
            if is_multipart and num_parts > 0:
                # Iniziamo la prima parte del multi-part
                next_part_file = os.path.join(TMP_DIR, "audio_part1.wav")
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
                state["current_segment"] = "voice_single"
                write_state_files(state)
                return {
                    "action": "PLAY_VOICE_MIX",
                    "voice_file": voice_file,
                    "music_file": music_file,
                    "character": block_type,
                    "title": title,
                    "segment": "Completo"
                }
            
            # Se l'audio non è ancora pronto, dice al regista di aspettare o rigenerare
            return {"action": "WAIT_OR_GENERATE", "character": block_type, "title": title, "time_key": state.get("scheduled_slot")}

        elif current_segment.startswith("voice_part_"):
            # Gestione del sequenziamento multi-part delle rubriche
            try:
                current_part_idx = int(current_segment.split("_")[-1])
            except ValueError:
                current_part_idx = 1
                
            if current_part_idx < num_parts:
                next_part_idx = current_part_idx + 1
                next_part_file = os.path.join(TMP_DIR, f"audio_part{next_part_idx}.wav")
                
                # Prima di mandare in onda la prossima parte, riproduciamo 1 brano intermedio di stacco
                # Per non saltare il sequenziamento, creiamo uno stato intermedio di stacco musicale
                state["current_segment"] = f"music_stacco_{current_part_idx}_to_{next_part_idx}"
                write_state_files(state)
                
                music_file = self._select_non_repeated_music()
                if music_file:
                    add_music_track(music_file)
                    return {
                        "action": "PLAY_MUSIC",
                        "file": music_file,
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
            # Rientriamo dallo stacco musicale alla parte successiva del parlato
            parts = current_segment.split("_")
            next_part_idx = int(parts[-1])
            next_part_file = os.path.join(TMP_DIR, f"audio_part{next_part_idx}.wav")
            
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
            state["current_segment"] = "music_rotation_until_deadline"
            write_state_files(state)
            
            deadline = schedule_deadline(next_time)
            if datetime.datetime.now() >= deadline:
                return {"action": "TRIGGER_NEXT_BLOCK"}
                
            music_file = self._select_non_repeated_music()
            if music_file:
                add_music_track(music_file)
                return {
                    "action": "PLAY_MUSIC",
                    "file": music_file,
                    "label": "music_rotation"
                }
            else:
                return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 5}
                
        return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}

    def _handle_podcast_progression(self, state, title, current_segment, next_time):
        """
        Gestione specifica per la rubrica Podcast a due voci (Fase MVP 3.5).
        Il podcast ha un numero di parti fisso (solitamente 3) intercalate da musica.
        """
        # La logica del podcast cerca i file in TMP_DIR (audio_part1.wav, audio_part2.wav, etc.)
        voice_part_1 = os.path.join(TMP_DIR, "audio_part1.wav")
        voice_part_2 = os.path.join(TMP_DIR, "audio_part2.wav")
        voice_part_3 = os.path.join(TMP_DIR, "audio_part3.wav")
        
        has_3_parts = os.path.exists(voice_part_1) and os.path.exists(voice_part_2) and os.path.exists(voice_part_3)
        has_2_parts = os.path.exists(voice_part_1) and os.path.exists(voice_part_2) and not os.path.exists(voice_part_3)
        
        num_podcast_parts = 3 if has_3_parts else (2 if has_2_parts else 0)
        
        if current_segment == "intro" or current_segment == "init":
            if num_podcast_parts > 0:
                state["current_segment"] = "podcast_part_1"
                write_state_files(state)
                # Il podcast ha Giulia e Marco (multi-speaker) già pre-mixati senza musica di sottofondo o con un leggero mix
                # Per non coprire i due speaker, li riproduciamo in modalità classica s16le pulita o con un mix leggerissimo
                return {
                    "action": "PLAY_VOICE",
                    "file": voice_part_1,
                    "character": "podcast",
                    "title": title,
                    "segment": "Podcast Parte 1"
                }
            else:
                return {"action": "WAIT_OR_GENERATE", "character": "podcast", "title": title, "time_key": state.get("scheduled_slot")}
                
        elif current_segment.startswith("podcast_part_"):
            try:
                curr_part = int(current_segment.split("_")[-1])
            except ValueError:
                curr_part = 1
                
            if curr_part < num_podcast_parts:
                next_part = curr_part + 1
                state["current_segment"] = f"podcast_music_stacco_{curr_part}_to_{next_part}"
                write_state_files(state)
                
                # Mettiamo un brano intero di stacco tra le parti del talk show podcast
                music_file = self._select_non_repeated_music()
                if music_file:
                    add_music_track(music_file)
                    return {
                        "action": "PLAY_MUSIC",
                        "file": music_file,
                        "label": "stacco_musicale_podcast"
                    }
                    
            state["current_segment"] = "podcast_closing"
            write_state_files(state)
            return {
                "action": "PLAY_JINGLE",
                "file": self.classic_jingle,
                "label": "stacco_uscita_podcast",
                "next_segment": "music_rotation_until_deadline"
            }
            
        elif current_segment.startswith("podcast_music_stacco_"):
            parts = current_segment.split("_")
            next_part = int(parts[-1])
            next_file = os.path.join(TMP_DIR, f"audio_part{next_part}.wav")
            
            if os.path.exists(next_file):
                state["current_segment"] = f"podcast_part_{next_part}"
                write_state_files(state)
                return {
                    "action": "PLAY_VOICE",
                    "file": next_file,
                    "character": "podcast",
                    "title": title,
                    "segment": f"Podcast Parte {next_part}"
                }
            else:
                state["current_segment"] = "podcast_closing"
                write_state_files(state)
                return {"action": "PLAY_SILENCE_FALLBACK", "seconds": 2}
                
        elif current_segment == "podcast_closing" or current_segment == "music_rotation_until_deadline":
            state["current_segment"] = "music_rotation_until_deadline"
            write_state_files(state)
            
            deadline = schedule_deadline(next_time)
            if datetime.datetime.now() >= deadline:
                return {"action": "TRIGGER_NEXT_BLOCK"}
                
            music_file = self._select_non_repeated_music()
            if music_file:
                add_music_track(music_file)
                return {
                    "action": "PLAY_MUSIC",
                    "file": music_file,
                    "label": "music_rotation"
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
            # Recuperiamo i tempi dal palinsesto
            _, _, _, next_time, current_time, _ = get_current_block_info()
            
            if current_time == interrupted_slot:
                # Calcola quanti minuti mancano al prossimo blocco
                deadline = schedule_deadline(next_time)
                now = datetime.datetime.now()
                time_remaining = (deadline - now).total_seconds()
                
                # Calcola la durata totale dello slot
                # (Semplificazione: ipotizziamo una durata standard di 30 o 60 minuti se non calcolabile)
                total_duration = 1800.0  # 30 minuti di default
                
                # Se manca ancora almeno il 40% del tempo dello slot, lo riprendiamo
                if time_remaining >= (total_duration * 0.40):
                    print(f"🔄 [DirectorAgent] Ripristino slot interrotto '{interrupted_title}' (Fascia delle {interrupted_slot}) - Rimangono {time_remaining/60:.1f} minuti (>=40%).")
                    restored_state = {
                        "status": "ON_AIR",
                        "current_block": interrupted_block,
                        "current_title": interrupted_title,
                        "current_segment": "music_rotation_until_deadline", # riprendiamo con musica
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
