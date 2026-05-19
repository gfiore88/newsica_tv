# ADR 0018: Synchronous Interrupt Playout to Eliminate Silent Gaps

## Context & Problem
Previously, when the system processed a high-priority event such as an `HOURLY_CHIME_READY` or `BREAKING_NEWS_READY` command, the director performed the following steps asynchronously:
1. Stopped the currently playing process using `stop_current_process()`.
2. Cleared the entire audio playout queue using `clear_audio_queue()`.
3. Spawned a background thread to play the chime or breaking news.
4. Set an interrupt event `schedule_interrupt_event.set()` which forced the background generator thread (`generator_worker()`) to abort and restart its current cycle.

This created two critical issues:
- **For Hourly Chimes (5 seconds)**: The entire regular playout queue was discarded. While the chime played, the generator started rebuilding the next block from scratch. Rebuilding requires running an LLM prompt (Ollama: ~15s) and speech synthesis (Kokoro: ~10s). Because these processes take around 25 seconds combined and the chime only lasts 5 seconds, a massive **20-second silent gap** was broadcasted on the live stream.
- **For Breaking News (20 seconds)**: The generator thread remained idle in a `while breaking_news_active` polling loop. It waited until the breaking news was fully played and deleted from the queue. Only then did it wake up to generate the next regular block from scratch. This caused another **25-second silent gap** immediately following the breaking news.

## Selected Solution: Option A (Queue Preservation & Instant Playout Pausing)
To achieve absolute broadcast-grade seamlessness, we restructured both interrupt handlers in `director.py` to use a **Synchronous Playout & Queue Preservation** design:

1. **Hourly Chimes: Queue Preservation and In-Line Injection**
   - We no longer call `stop_current_process()`, `clear_audio_queue()`, or `schedule_interrupt_event.set()` for chimes.
   - When the chime is ready, the main loop halts reading from the queue and directly reads/writes the chime chunks to the FFmpeg `fifo` pipe synchronously.
   - Because the main loop blocks for the 5-second duration of the chime, it naturally regulates the streaming rate.
   - The graphics update to show "SEGNALE ORARIO" and restore the previous state immediately afterward.
   - Once the chime finishes, the main loop naturally resumes reading from `audio_queue`, starting exactly where the regular program paused. **Silent gap: 0 seconds.**

2. **Breaking News: Queue Preservation and In-Line Injection**
   - Just like the hourly chime, we no longer stop the regular generator process, clear the queue, or trigger the generator reset when a breaking news is ready.
   - The main loop temporarily pauses reading from the regular queue, updates the stream graphics/colors to "🚨 ULTIM'ORA", and streams the breaking news file directly to the FIFO pipe synchronously.
   - The background generator thread is completely unaffected and continues to buffer future parts of the palinsesto into the queue.
   - The moment the breaking news bulletin ends, the stream graphics are restored to their previous state and the main loop immediately resumes reading from the regular queue.
   - The interrupted song or show speech resumes playing from the exact millisecond where it was paused. **Silent gap: 0 seconds.**

## Consequences
- **Zero Silent Gaps**: Eliminates all empty spaces and audio blackouts on the stream, ensuring a highly professional, uninterrupted broadcast.
- **Instant Resumption**: Allows the stream to return **immediately** to the pre-existing flow (resuming the exact song or conductor speech) the moment the interrupt ends.
- **Extreme Architecture Cohesion**: Both high-priority interrupt types (Hourly Chimes and Breaking News) now share the exact same high-performance, robust synchronous pipeline.
