import os
import datetime
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
from newsica.broadcast.shorts_reconcile_policy import ShortsReconcilePolicy
from newsica.broadcast.interrupt_recovery_policy import InterruptRecoveryPolicy
from newsica.broadcast.special_broadcast_policy import SpecialBroadcastPolicy
from newsica.shorts.daily_planner import DailyShortsPlanner

EVENING_PODCAST_SLOT = "20:00"
EVENING_PODCAST_TITLE = "Newsica Podcast - Dopo Sera"
EVENING_PODCAST_MIN_REMAINING_SECONDS = 20 * 60

class DirectorAgent:
    def __init__(self, playout=None):
        self.playout = playout
        # Carica percorsi jingle
        self.classic_jingle = str(CLASSIC_JINGLE_FILE)
        self.shorts_planner = DailyShortsPlanner()
        self.shorts_reconcile_policy = ShortsReconcilePolicy(
            self.shorts_planner,
            breaking_probe_interval_seconds=int(os.getenv("SHORTS_BREAKING_SCAN_INTERVAL_SECONDS", "600")),
        )
        self.interrupt_recovery_policy = InterruptRecoveryPolicy()
        self.special_broadcast_policy = SpecialBroadcastPolicy()

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
        self._reconcile_daily_shorts_plan_if_needed()
        self._reconcile_breaking_shorts_if_needed()
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

    def _reconcile_daily_shorts_plan_if_needed(self):
        self.shorts_reconcile_policy.reconcile_daily_if_needed()

    def _reconcile_breaking_shorts_if_needed(self):
        self.shorts_reconcile_policy.reconcile_breaking_if_needed()

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
        return self.special_broadcast_policy.handle(
            state=state,
            tmp_dir=TMP_DIR,
            assets_dir=ASSETS_DIR,
            write_state_files=write_state_files,
            select_non_repeated_music=self._select_non_repeated_music,
        )

    def notify_interrupt(self, reason, severity_score=0):
        """
        Forza un'interruzione di regia per gestire una breaking news o un'edizione straordinaria.
        """
        return self.interrupt_recovery_policy.notify_interrupt(
            reason=reason,
            severity_score=severity_score,
            get_current_state=get_current_state,
            write_state_files=write_state_files,
            log_decision=log_decision,
            assets_dir=ASSETS_DIR,
            classic_jingle=self.classic_jingle,
        )

    def handle_restore_after_interrupt(self):
        """
        Ripristina il palinsesto ordinario seguendo la regola del 40% di durata residua.
        """
        self.interrupt_recovery_policy.handle_restore_after_interrupt(
            get_current_state=get_current_state,
            write_state_files=write_state_files,
            get_current_block_info=get_current_block_info,
            schedule_deadline=schedule_deadline,
            log_decision=log_decision,
        )

    def restore_after_immediate_event(self, previous_state=None):
        """
        Riallinea la regia al blocco schedulato corrente dopo un evento immediato.
        Evita di ripristinare ciecamente uno stato stantio che può perdere theme/titolo.
        """
        self.interrupt_recovery_policy.restore_after_immediate_event(
            previous_state=previous_state,
            get_wallclock_schedule_key=get_wallclock_schedule_key,
            get_current_block_info=get_current_block_info,
            write_state_files=write_state_files,
            resolve_music_slot_editorial_guardrail=self._resolve_music_slot_editorial_guardrail,
            log_decision=log_decision,
        )

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
