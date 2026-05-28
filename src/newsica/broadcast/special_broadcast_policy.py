import os

from newsica.domain.playout_events import PlayMusicEvent, PlaySilenceFallbackEvent, PlayVoiceMixEvent


class SpecialBroadcastPolicy:
    def handle(
        self,
        *,
        state,
        tmp_dir,
        assets_dir,
        write_state_files,
        select_non_repeated_music,
    ):
        current_segment = state.get("current_segment", "init")
        bn_file = os.path.join(tmp_dir, "breaking_news.wav")

        special_theme = os.path.join(assets_dir, "music", "special_broadcast_theme.mp3")
        if not os.path.exists(special_theme):
            special_theme = select_non_repeated_music()

        if current_segment in {"init", "intro"}:
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
            return PlaySilenceFallbackEvent(5)

        if current_segment == "broadcast_body":
            state["current_segment"] = "broadcast_waiting"
            write_state_files(state)
            return PlayMusicEvent(special_theme, "attesa_edizione_straordinaria")

        if current_segment == "broadcast_waiting":
            state["current_segment"] = "intro"
            write_state_files(state)
            return PlaySilenceFallbackEvent(5)

        return PlaySilenceFallbackEvent(2)
