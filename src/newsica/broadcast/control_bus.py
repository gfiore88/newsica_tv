import os

class ControlCommand:
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs

def poll_control_file(control_file):
    """
    Legge il file di controllo (se presente), ne estrae il comando,
    lo cancella e restituisce un oggetto ControlCommand.
    Restituisce None se non ci sono comandi.
    """
    if not os.path.exists(control_file):
        return None
        
    try:
        with open(control_file, "r") as f:
            cmd_raw = f.read().strip()
        os.remove(control_file)
        
        if not cmd_raw:
            return None
            
        if cmd_raw == "FORCE_NEXT":
            return ControlCommand("FORCE_NEXT")
        elif cmd_raw.startswith("FORCE_INDEX_"):
            target_idx = int(cmd_raw.split("_")[2])
            return ControlCommand("FORCE_INDEX", target_idx=target_idx)
        elif cmd_raw == "REGEN_SCHEDULE":
            return ControlCommand("REGEN_SCHEDULE")
        elif cmd_raw.startswith("HOURLY_CHIME_READY"):
            parts = cmd_raw.split("|")
            chime_file = parts[1] if len(parts) > 1 else None
            return ControlCommand("HOURLY_CHIME_READY", chime_file=chime_file)
        elif cmd_raw == "TRIGGER_BREAKING_NEWS":
            return ControlCommand("TRIGGER_BREAKING_NEWS")
        elif cmd_raw == "TRIGGER_SPECIAL_BROADCAST_TEST":
            return ControlCommand("TRIGGER_SPECIAL_BROADCAST_TEST")
        elif cmd_raw.startswith("PLAY_PODCAST_IMMEDIATE"):
            parts = cmd_raw.split("|", 2)
            podcast_file = parts[1] if len(parts) > 1 else None
            podcast_title = parts[2] if len(parts) > 2 else "Newsica Podcast"
            return ControlCommand("PLAY_PODCAST_IMMEDIATE", podcast_file=podcast_file, podcast_title=podcast_title)
        elif cmd_raw.startswith("PLAY_NEWS_IMMEDIATE"):
            parts = cmd_raw.split("|", 2)
            news_file = parts[1] if len(parts) > 1 else None
            news_title = parts[2] if len(parts) > 2 else "TG Newsica"
            return ControlCommand("PLAY_NEWS_IMMEDIATE", news_file=news_file, news_title=news_title)
        elif cmd_raw.startswith("BREAKING_NEWS_READY"):
            parts = cmd_raw.split("|")
            bn_file = parts[1] if len(parts) > 1 else ""
            severity_score = int(parts[2]) if len(parts) > 2 else 0
            reason = parts[3] if len(parts) > 3 else "Valutazione ordinaria"
            return ControlCommand("BREAKING_NEWS_READY", bn_file=bn_file, severity_score=severity_score, reason=reason)
        elif cmd_raw in ["REVOKE_SPECIAL_BROADCAST", "END_SPECIAL_BROADCAST"]:
            return ControlCommand("REVOKE_SPECIAL_BROADCAST")
        else:
            return ControlCommand("UNKNOWN", raw=cmd_raw)
            
    except Exception as e:
        print(f"⚠️ Errore parsing command from control file: {e}")
        return None
