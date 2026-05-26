import os
import json
import datetime
import random
import wave
from newsica.config.paths import TMP_DIR, RUNTIME_DIR, ASSETS_DIR
from newsica.utils.audit_logger import log_decision
from newsica.domain.playout_events import (
    PlayJingleEvent,
    PlayMusicDeadlineEvent,
    PlayMusicEvent,
    PlayoutEvent,
    PlaySilenceFallbackEvent,
    PlayVoiceEvent,
    PlayVoiceMixEvent,
    TriggerNextBlockEvent,
)

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
from newsica.storage.repositories.editorial_memory_repository import (
    add_title,
    add_rubric,
    add_music_track,
    is_title_recent,
    is_music_track_recent,
    should_short_intro,
    update_last_intro
)
from newsica.audio.jingles import get_jingle_for_block, CLASSIC_JINGLE_FILE
from newsica.audio.music_library import DEFAULT_THEMED_MIN_TRACKS, GENERIC_THEMELESS_MUSIC_TITLE, MusicLibrary

EVENING_PODCAST_SLOT = "20:00"
EVENING_PODCAST_TITLE = "Newsica Podcast - Dopo Sera"
EVENING_PODCAST_MIN_REMAINING_SECONDS = 20 * 60

class DirectorAgent:
    def __init__(self, playout=None):
        self.playout = playout
        # Carica percorsi jingle
        self.classic_jingle = str(CLASSIC_JINGLE_FILE)

    def _resolve_music_slot_editorial_guardrail(self, block_type, title, theme):
        if block_type != "music_only" or not theme:
            return title, theme

        library = MusicLibrary()
        if library.has_minimum_theme_catalog(theme, minimum=DEFAULT_THEMED_MIN_TRACKS):
            return title, theme

        available = library.count_ai_tracks_for_theme(theme)
        print(
            f"⚠️ [DirectorAgent] Catalogo tematico insufficiente per '{title}' "
            f"(theme={theme}, disponibili={available}, richiesti={DEFAULT_THEMED_MIN_TRACKS}). "
            f"Degrado editoriale a fascia musicale generica."
        )
        log_decision(
            "DirectorAgent",
            f"Catalogo tematico insufficiente per '{title}' (theme={theme}, disponibili={available}, "
            f"richiesti={DEFAULT_THEMED_MIN_TRACKS}). Degrado a fascia musicale generica.",
            level="PLAYOUT",
        )
        return GENERIC_THEMELESS_MUSIC_TITLE, None
        
    def decide_next_action(self, manual_block_override_index=None):
        """
        Analizza lo stato corrente e il palinsesto per determinare l'azione immediata.
        Restituisce un dizionario contenente l'azione e i relativi parametri.
        """
        state = get_current_state()
        status = state.get("status", "OFFLINE")
        current_block = state.get("current_block", "")
        
        # 1. Se siamo in SPECIAL_BROADCAST, gestiamo la copertura speciale
        if status == "SPECIAL_BROADCAST":
            res = self._handle_special_broadcast(state)
            _, _, _, _, _, active_idx = get_current_block_info(manual_block_override_index)
            return self._attach_active_index(res, active_idx)
            
        # 2. Leggiamo il blocco programmato dal palinsesto
        block_type, title, next_title, next_time, current_time, active_idx = get_current_block_info(manual_block_override_index)
        
        # Se lo stato attuale è OFFLINE o non coincide con il blocco corrente, inizializziamo la transizione
        if status == "OFFLINE" or state.get("scheduled_slot") != current_time:
            print(f"🎬 [DirectorAgent] Inizializzazione fascia palinsesto: {current_time} ({title})")
            log_decision("DirectorAgent", f"Inizializzazione fascia palinsesto: {current_time} ({title})", level="PLAYOUT")
            res = self._initialize_scheduled_block(block_type, title, next_title, next_time, current_time)
        else:
            # 3. Gestiamo la progressione interna del blocco attivo
            res = self._progress_current_block(state, block_type, title, next_title, next_time, current_time)
            
        return self._attach_active_index(res, active_idx)

    def _attach_active_index(self, result, active_idx):
        if isinstance(result, list):
            return [event.with_active_idx(active_idx) for event in result]
        if isinstance(result, PlayoutEvent):
            return result.with_active_idx(active_idx)
        return result

    def _initialize_scheduled_block(self, block_type, title, next_title, next_time, current_time):
        """
        Prepara il passaggio a un nuovo blocco di palinsesto e delega al PlayoutPlanner.
        """
        self._clear_transient_audio()
        
        theme = None
        try:
            from schedule_generator import get_current_schedule
            schedule_data = get_current_schedule()
            theme = schedule_data.get(current_time, {}).get("theme")
            if theme:
                print(f"🎬 [DirectorAgent] Rilevato tema per lo show '{title}': {theme}")
        except Exception as e:
            print(f"⚠️ Errore lettura tema dal palinsesto: {e}")

        title, theme = self._resolve_music_slot_editorial_guardrail(block_type, title, theme)

        new_state = {
            "status": "ON_AIR",
            "current_block": block_type,
            "current_title": title,
            "current_segment": "init",
            "next_block": next_title,
            "next_start": next_time,
            "scheduled_slot": current_time,
            "theme": theme,
            "breaking_news_available": False,
            "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }
        write_state_files(new_state)
        
        # Se è un podcast serale o un podcast generico, manteniamo la vecchia logica di fallback iterativa per ora
        if block_type == "podcast" or (block_type == "news" and current_time == EVENING_PODCAST_SLOT):
            jingle_file, jingle_label = get_jingle_for_block(block_type)
            return PlayJingleEvent(jingle_file, jingle_label, next_segment="intro")
        
        # Generiamo la playlist con il Planner per le rubriche standard e la musica
        from newsica.broadcast.planner import PlayoutPlanner
        planner = PlayoutPlanner(self._select_non_repeated_music)
        events = planner.plan_block(block_type, title, next_time, current_time, theme)
        return events

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
        Gestisce la progressione interna dei segmenti del blocco attivo (legacy per podcast e fallback).
        """
        current_segment = state.get("current_segment", "init")

        # Guard per slot passati forzati via FORCE_INDEX:
        # Se lo scheduled_slot è diverso dal wallclock corrente, significa che stiamo
        # riproducendo uno slot passato su override manuale. Una volta esaurita la coda
        # eventi del PlayoutPlanner (arriviamo qui), torniamo al palinsesto normale.
        # Senza questo check, schedule_deadline() restituisce "domani" per orari passati,
        # generando un loop musicale infinito che non torna mai al wallclock.
        wallclock_slot = get_wallclock_schedule_key()
        scheduled_slot = state.get("scheduled_slot", "")
        if scheduled_slot and wallclock_slot and scheduled_slot != wallclock_slot:
            if scheduled_slot < wallclock_slot:
                print(
                    f"⏰ [DirectorAgent] Slot forzato passato '{title}' ({scheduled_slot}) completato. "
                    f"Ripristino palinsesto corrente ({wallclock_slot})."
                )
                log_decision(
                    "DirectorAgent",
                    f"Slot forzato passato '{title}' ({scheduled_slot}) completato. Torno al wallclock ({wallclock_slot}).",
                    level="PLAYOUT",
                )
                return TriggerNextBlockEvent()

        if block_type == "music_only":
            deadline = schedule_deadline(next_time)
            if datetime.datetime.now() >= deadline:
                return TriggerNextBlockEvent()

            theme = state.get("theme")
            music_file = self._select_non_repeated_music(theme=theme)
            if music_file:
                add_music_track(music_file)
                return PlayMusicDeadlineEvent(music_file, deadline, "music_rotation")

            return PlaySilenceFallbackEvent(2)
            
        elif block_type == "podcast" or (block_type == "news" and current_time == EVENING_PODCAST_SLOT):
            return self._handle_podcast_progression(state, title, current_segment, next_time)
            
        else:
            # Rubriche standard già planate dal PlayoutPlanner:
            # se arriviamo qui significa che il planner ha svuotato la coda, 
            # passiamo al prossimo blocco.
            deadline = schedule_deadline(next_time)
            if datetime.datetime.now() >= deadline:
                return TriggerNextBlockEvent()
                
            if current_segment == "music_rotation_until_deadline":
                theme = state.get("theme")
                music_file = self._select_non_repeated_music(theme=theme)
                if music_file:
                    add_music_track(music_file)
                    return PlayMusicDeadlineEvent(music_file, deadline, "music_rotation")
                    
            return PlaySilenceFallbackEvent(2)




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
        has_valid_audio = os.path.exists(voice_file)
        manifest = {}  # inizializzato qui per evitare UnboundLocalError nel path senza manifest

        if has_valid_audio:
            from newsica.storage.repositories.audio_metadata_repository import get_metadata
            try:
                meta_row = get_metadata(voice_file)
                if meta_row and meta_row.get("metadata"):
                    manifest = meta_row["metadata"]
                    if manifest.get("character") != "podcast":
                        print(
                            f"⚠️ [DirectorAgent] Podcast pronto non coerente per {scheduled_slot}: "
                            f"atteso podcast, trovato {manifest}."
                        )
                        has_valid_audio = False
            except Exception:
                pass
                print(f"⚠️ [DirectorAgent] Podcast pronto senza manifest valido per {scheduled_slot}. Attendo rigenerazione.")
                has_valid_audio = False

        if current_segment in {"intro", "init"} or (current_segment == "music_rotation_until_deadline" and not state.get("podcast_played")):
            if has_valid_audio and not state.get("podcast_played"):
                state["current_segment"] = "podcast_playing"
                state["podcast_played"] = True
                write_state_files(state)
                return PlayVoiceEvent(
                    voice_file,
                    "podcast",
                    manifest.get("title", title) if manifest else title,
                    "Completo",
                )
            # Se l'audio non è pronto, inneschiamo un fallback musicale.
            print(f"⚠️ [DirectorAgent] Podcast non pronto per slot {scheduled_slot}. Uso musica finché l'asset non arriva.")
            state["current_segment"] = "music_rotation_until_deadline"
            state["current_title"] = "Intervallo Musicale - In attesa del Podcast"
            write_state_files(state)
            
            theme = state.get("theme")
            music_file = self._select_non_repeated_music(theme=theme)
            if music_file:
                add_music_track(music_file)
                deadline = schedule_deadline(next_time)
                return PlayMusicDeadlineEvent(music_file, deadline, "fallback_non_pronto")
            return PlaySilenceFallbackEvent(2)

        elif current_segment == "podcast_playing":
            state["current_segment"] = "podcast_closing"
            write_state_files(state)
            return PlayJingleEvent(
                self.classic_jingle,
                "stacco_uscita_podcast",
                next_segment="music_rotation_until_deadline",
            )
                
        elif current_segment == "podcast_closing" or current_segment == "music_rotation_until_deadline":
            state["current_segment"] = "music_rotation_until_deadline"
            write_state_files(state)
            
            # Check if this is a past manual override block
            current_slot = state.get("scheduled_slot")
            wallclock_slot = get_wallclock_schedule_key()
            if current_slot and wallclock_slot and current_slot != wallclock_slot:
                if current_slot < wallclock_slot:
                    print(f"⏰ [DirectorAgent] Past override slot '{title}' completed. Returning to normal schedule.")
                    return TriggerNextBlockEvent()

            deadline = schedule_deadline(next_time)
            if datetime.datetime.now() >= deadline:
                return TriggerNextBlockEvent()
                
            time_remaining = (deadline - datetime.datetime.now()).total_seconds()
            trigger_ai_music_gen = time_remaining >= 180
                
            theme = state.get("theme")
            music_file = self._select_non_repeated_music(theme=theme)
            if music_file:
                add_music_track(music_file)
                return PlayMusicEvent(
                    music_file,
                    "music_rotation",
                    trigger_ai_music_gen=trigger_ai_music_gen,
                    theme=theme,
                )
            else:
                return PlaySilenceFallbackEvent(5)
                
        return PlaySilenceFallbackEvent(2)

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
                return PlayVoiceMixEvent(
                    voice_file=bn_file,
                    music_file=special_theme,
                    character="breaking_news",
                    title="EDIZIONE STRAORDINARIA",
                    segment="Bollettino Speciale",
                )
            else:
                return PlaySilenceFallbackEvent(5)
                
        elif current_segment == "broadcast_body":
            # Finito il bollettino, se non c'è una revoca manuale o se non sono passati abbastanza minuti,
            # riproduciamo musica di attesa o un altro jingle e poi ripetiamo il ciclo
            state["current_segment"] = "broadcast_waiting"
            write_state_files(state)
            
            # Sfondi tesi di attesa
            return PlayMusicEvent(special_theme, "attesa_edizione_straordinaria")
            
        elif current_segment == "broadcast_waiting":
            # Ripete il bollettino speciale aggiornato
            state["current_segment"] = "intro"
            write_state_files(state)
            return PlaySilenceFallbackEvent(5)
            
        return PlaySilenceFallbackEvent(2)

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
                
            return PlayJingleEvent(jingle_file, "jingle_straordinaria", next_segment="intro")
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

    def _select_non_repeated_music(self, theme=None):
        """
        Seleziona un brano musicale randomico che non è presente nella memoria recente.
        """
        if not self.playout:
            # Fallback se playout non è agganciato
            return None
            
        # Prova fino a 10 volte per trovare un brano non riprodotto di recente
        for _ in range(10):
            music_file = self.playout.get_random_music(theme=theme, remember=False)
            if not music_file:
                break
            if not is_music_track_recent(music_file):
                return music_file
                
        # Se tutti i brani sono recenti, ne restituisce uno a caso per non interrompere l'audio
        return self.playout.get_random_music(theme=theme, remember=False)
