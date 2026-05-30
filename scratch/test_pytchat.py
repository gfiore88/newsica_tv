import pytchat
import time
import sys

video_id = "E3xazWYSkww"
print(f"Starting pytchat test for video_id: {video_id}")
try:
    chat = pytchat.create(video_id=video_id)
    if chat.is_alive():
        print("Pytchat is alive! Waiting 15 seconds for messages...")
        start_time = time.time()
        while chat.is_alive() and time.time() - start_time < 15:
            for c in chat.get().sync_items():
                print(f"[{c.datetime}] {c.author.name}: {c.message}")
            time.sleep(1)
        print("Test completed.")
    else:
        print("Pytchat failed to start (is_alive is False).")
except Exception as e:
    print(f"Exception during pytchat test: {e}")
