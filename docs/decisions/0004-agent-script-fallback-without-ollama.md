# 0004 - Agent script fallback without Ollama

Date: 2026-05-18

## Status

Accepted

## Context

The live director rotates `news`, `sport`, and `meteo`, but `llm_processor.py`
depends on Ollama at `localhost:11434`. When Ollama is unavailable, the process
exited with an error while `director.py` continued to run TTS against the last
existing `tmp/script.txt`. This could make all agents read the same stale script.

RSS fetching also used `feedparser.parse(url)` without an explicit timeout,
which can delay the pipeline when a feed is slow.

## Decision

`llm_processor.py` now writes a deterministic local fallback script for the
selected character when Ollama is unavailable or returns an empty response.
`director.py` now checks subprocess return codes so it does not silently proceed
after a failed step. `scraper.py` fetches RSS feeds through `requests` with an
explicit timeout before parsing.

The default Ollama model is `gemma3:12b`, configurable through `OLLAMA_MODEL`.
`qwen3` models were avoided for this pipeline because they can emit internal
thinking before a useful final response, causing empty or delayed scripts.

## Consequences

The stream keeps rotating coherent `news`, `sport`, and `meteo` blocks even when
Ollama is offline. Quality is lower than the LLM rewrite, but the live schedule
does not collapse into stale content.
