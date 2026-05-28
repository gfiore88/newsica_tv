import datetime
import os

from newsica.domain.playout_events import PlayJingleEvent


class InterruptRecoveryPolicy:
    def notify_interrupt(
        self,
        *,
        reason,
        severity_score,
        get_current_state,
        write_state_files,
        log_decision,
        assets_dir,
        classic_jingle,
    ):
        state = get_current_state()

        if severity_score >= 90:
            print(f"🚨 [DirectorAgent] RILEVATO EVENTO ECCEZIONALE (Score {severity_score}). Attivo SPECIAL_BROADCAST!")
            log_decision(
                "DirectorAgent",
                f"RILEVATO EVENTO ECCEZIONALE (Score {severity_score}). Attivo SPECIAL_BROADCAST!",
                level="BREAKING",
            )

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
                "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }
            write_state_files(special_state)

            jingle_file = os.path.join(assets_dir, "jingles", "jingle_breaking_news.mp3")
            if not os.path.exists(jingle_file):
                jingle_file = classic_jingle

            return PlayJingleEvent(jingle_file, "jingle_straordinaria", next_segment="intro")

        print(f"📢 [DirectorAgent] Rilevata Breaking News ordinaria (Score {severity_score}).")
        return None

    def handle_restore_after_interrupt(
        self,
        *,
        get_current_state,
        write_state_files,
        get_current_block_info,
        schedule_deadline,
        log_decision,
    ):
        state = get_current_state()
        status = state.get("status", "OFFLINE")

        if status != "SPECIAL_BROADCAST":
            return

        interrupted_slot = state.get("interrupted_slot")
        interrupted_block = state.get("interrupted_block", "music_only")
        interrupted_title = state.get("interrupted_title", "")

        if not interrupted_slot:
            write_state_files({"status": "OFFLINE"})
            return

        try:
            _, _, _, next_time, current_time, _ = get_current_block_info()

            if current_time == interrupted_slot:
                deadline = schedule_deadline(next_time)
                now = datetime.datetime.now()
                time_remaining = (deadline - now).total_seconds()

                try:
                    slot_start_hour, slot_start_min = map(int, interrupted_slot.split(":"))
                    slot_start = now.replace(hour=slot_start_hour, minute=slot_start_min, second=0, microsecond=0)
                    if slot_start > now:
                        slot_start -= datetime.timedelta(days=1)
                    total_duration = (deadline - slot_start).total_seconds()
                except Exception:
                    total_duration = 1800.0

                min_threshold = max(300.0, total_duration * 0.20)

                restored_state = {
                    "status": "ON_AIR",
                    "current_block": interrupted_block,
                    "current_title": interrupted_title,
                    "current_segment": "music_rotation_until_deadline",
                    "next_block": state.get("next_block", ""),
                    "next_start": state.get("next_start", ""),
                    "scheduled_slot": interrupted_slot,
                    "breaking_news_available": False,
                    "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                }

                if time_remaining >= min_threshold:
                    print(
                        f"🔄 [DirectorAgent] Ripristino slot interrotto '{interrupted_title}' "
                        f"(Fascia delle {interrupted_slot}) - Rimangono {time_remaining/60:.1f} min "
                        f"su {total_duration/60:.0f} min totali."
                    )
                    log_decision(
                        "DirectorAgent",
                        f"Ripristino slot interrotto '{interrupted_title}' (residuo {time_remaining/60:.1f} min).",
                        level="RESTORE",
                    )
                    write_state_files(restored_state)
                    log_decision("DirectorAgent", f"Ripristinato il blocco: {interrupted_title}", level="INIT")
                    return

                print(
                    f"⏭️ [DirectorAgent] Slot quasi scaduto ({time_remaining/60:.1f} min residui, "
                    f"soglia {min_threshold/60:.1f} min). Attendo naturale cambio fascia."
                )
                log_decision(
                    "DirectorAgent",
                    f"Salto ripristino '{interrupted_title}'. Tempo residuo troppo basso ({time_remaining/60:.1f} min).",
                    level="RESTORE",
                )
                write_state_files(restored_state)
                return
        except Exception as e:
            print(f"⚠️ Errore durante il calcolo del ripristino: {e}")

        print("⏭️ [DirectorAgent] Lo slot interrotto è quasi scaduto (<40% residuo). Salto direttamente alla programmazione successiva.")
        write_state_files({"status": "OFFLINE"})

    def restore_after_immediate_event(
        self,
        *,
        previous_state,
        get_wallclock_schedule_key,
        get_current_block_info,
        write_state_files,
        resolve_music_slot_editorial_guardrail,
        log_decision,
    ):
        previous_state = dict(previous_state or {})
        wallclock_slot = get_wallclock_schedule_key()
        previous_slot = previous_state.get("scheduled_slot")

        if previous_slot and previous_slot != wallclock_slot:
            print(
                f"⏭️ [DirectorAgent] Evento immediato terminato su slot cambiato "
                f"({previous_slot} -> {wallclock_slot}). Reinizializzo dal palinsesto."
            )
            write_state_files({"status": "OFFLINE"})
            return

        block_type, title, next_title, next_time, current_time, _ = get_current_block_info()
        theme = None
        try:
            from schedule_generator import get_current_schedule

            schedule_data = get_current_schedule()
            theme = schedule_data.get(current_time, {}).get("theme")
        except Exception:
            theme = None

        title, theme = resolve_music_slot_editorial_guardrail(block_type, title, theme)

        restored_state = {
            "status": "ON_AIR",
            "current_block": block_type,
            "current_title": title,
            "current_segment": "music_rotation_until_deadline",
            "next_block": next_title,
            "next_start": next_time,
            "scheduled_slot": current_time,
            "theme": theme,
            "breaking_news_available": False,
            "last_update": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if block_type == "podcast":
            restored_state["podcast_played"] = True

        print(
            f"🔄 [DirectorAgent] Ripristino dopo evento immediato sul blocco schedulato "
            f"{current_time} ({title})."
        )
        log_decision(
            "DirectorAgent",
            f"Ripristino dopo evento immediato sul blocco schedulato {current_time} ({title}).",
            level="RESTORE",
        )
        write_state_files(restored_state)
