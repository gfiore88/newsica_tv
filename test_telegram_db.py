from newsica.audio.telegram_voices import enqueue_voice

enqueue_voice(
    author_username="testuser",
    author_first_name="Test",
    file_id="123456",
    duration=10,
    original_path="/tmp/original.ogg",
    converted_path="/tmp/converted.wav"
)
print("Test voice enqueued in SQLite via wrapper!")
