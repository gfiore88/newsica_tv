from newsica.config.paths import BASE_DIR

PCM_SAMPLE_RATE = 24000
PCM_CHANNELS = 1
PCM_CHUNK_BYTES = 4096


def resolve_ffmpeg_cmd():
    candidates = [
        "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "ffmpeg",
    ]
    for candidate in candidates:
        if candidate == "ffmpeg" or (BASE_DIR / candidate).exists():
            return candidate
    return "ffmpeg"

