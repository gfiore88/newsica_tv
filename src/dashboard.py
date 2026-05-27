from flask import Flask, jsonify, render_template_string, request, send_file, send_from_directory
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env prima di qualsiasi altro modulo
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_base_dir, ".env"))

import json
import signal
import subprocess
import time
import numpy as np
import soundfile as sf
from schedule_generator import get_current_schedule, generate_schedule
from newsica.storage.repositories.ai_music_jobs_repository import enqueue_job
from newsica.audio.ai_music_runtime import resolve_ace_step_python
from newsica.audio.settings import resolve_ffmpeg_cmd
from newsica.audio.music_library import DEFAULT_RECENT_WINDOW, MusicLibrary
from newsica.audio.music_mode import (
    MUSIC_MODE_AI_ONLY,
    MUSIC_MODE_MIXED,
    read_music_mode,
    write_music_mode,
)
from newsica.agents.ai_integrator import AIIntegratorAgent
from newsica.agents.content_strategist import ContentStrategistAgent
from newsica.domain.characters import get_character, load_characters
from newsica.editorial.fallback_scripts import build_fallback_script
from newsica.editorial.source_filters import fallback_general_news, filter_items_for_character
from newsica.storage.database import get_connection
from newsica.storage.repositories.audio_metadata_repository import get_metadata


def _format_memory_value(raw_value):
    if raw_value is None:
        return {"text": "", "is_json": False, "summary": ""}
    if not isinstance(raw_value, str):
        raw_value = str(raw_value)
    trimmed = raw_value.strip()
    if not trimmed:
        return {"text": "", "is_json": False, "summary": ""}
    try:
        parsed = json.loads(trimmed)
    except Exception:
        return {"text": raw_value, "is_json": False, "summary": ""}

    summary = ""
    if isinstance(parsed, dict):
        interesting_keys = [
            key for key in (
                "status",
                "current_title",
                "current_block",
                "next_block",
                "author",
                "message",
                "mode",
                "theme",
                "requested_by",
                "requested_title",
            )
            if parsed.get(key)
        ]
        summary = " | ".join(f"{key}: {parsed[key]}" for key in interesting_keys[:4])
    elif isinstance(parsed, list):
        summary = f"{len(parsed)} elementi"

    return {
        "text": json.dumps(parsed, ensure_ascii=False, indent=2),
        "is_json": True,
        "summary": summary,
    }


def _resolve_track_display_title(asset_path):
    if not asset_path:
        return ""

    try:
        meta_row = get_metadata(os.path.realpath(asset_path))
    except Exception:
        meta_row = None

    if meta_row:
        artist = " ".join(str(meta_row.get("artist", "")).split())
        title = " ".join(str(meta_row.get("title", "")).split())
        if artist and title:
            return f"{artist} - {title}"
        if title:
            return title
        metadata = meta_row.get("metadata") or {}
        meta_title = " ".join(str(metadata.get("title", "")).split())
        if meta_title:
            return meta_title

    root, ext = os.path.splitext(asset_path)
    if ext.lower() in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}:
        sidecar_path = root + ".meta"
        if os.path.exists(sidecar_path):
            try:
                payload = json.loads(open(sidecar_path, "r", encoding="utf-8").read())
                sidecar_title = " ".join(str(payload.get("title", "")).split())
                if sidecar_title:
                    return sidecar_title
            except Exception:
                pass

    fallback_title = os.path.splitext(os.path.basename(asset_path))[0].replace("_", " ").strip()
    return " ".join(fallback_title.split())


def _decorate_history_row(row):
    item = dict(row)
    item["display_title"] = item.get("title") or "--"
    item["display_detail"] = item.get("segment") or item.get("block_type") or "--"

    if item.get("block_type") == "music":
        track_title = _resolve_track_display_title(item.get("asset_path"))
        if track_title:
            item["display_title"] = track_title
        label = item.get("title") or ""
        if label and label not in {"music_rotation", "fallback_non_pronto"}:
            item["display_detail"] = label
        elif item.get("segment"):
            item["display_detail"] = item["segment"]

    return item


def _load_rotation_runtime():
    history_path = os.path.join(RUNTIME_DIR, "music_rotation_history.json")
    blocks_path = os.path.join(RUNTIME_DIR, "music_rotation_blocks.json")

    try:
        history_payload = json.loads(open(history_path, "r", encoding="utf-8").read()) if os.path.exists(history_path) else {}
    except Exception:
        history_payload = {}

    try:
        blocks_payload = json.loads(open(blocks_path, "r", encoding="utf-8").read()) if os.path.exists(blocks_path) else {}
    except Exception:
        blocks_payload = {}

    recent_tracks = []
    for track_path in history_payload.get("recent_tracks", []):
        resolved = os.path.realpath(track_path)
        recent_tracks.append({
            "path": resolved,
            "display_title": _resolve_track_display_title(resolved),
            "filename": os.path.basename(resolved),
        })

    block_events = []
    for entry in reversed(blocks_payload.get("events", [])):
        blocked_tracks = []
        for track_path in entry.get("blocked_tracks", []):
            resolved = os.path.realpath(track_path)
            if not os.path.exists(resolved):
                continue
            blocked_tracks.append({
                "path": resolved,
                "display_title": _resolve_track_display_title(resolved),
                "filename": os.path.basename(resolved),
            })
        if not blocked_tracks:
            continue
        block_events.append({
            "timestamp": entry.get("timestamp"),
            "reason": entry.get("reason", "recent_window"),
            "recent_window": entry.get("recent_window", 0),
            "candidate_count": entry.get("candidate_count", 0),
            "blocked_count": len(blocked_tracks),
            "blocked_tracks": blocked_tracks,
        })

    return {
        "configured_window": DEFAULT_RECENT_WINDOW,
        "tracked_count": len(recent_tracks),
        "recent_tracks": recent_tracks,
        "block_events": block_events,
    }


def _normalize_short_hashtags(raw_hashtags):
    if not isinstance(raw_hashtags, list):
        return []
    hashtags = []
    seen = set()
    for value in raw_hashtags:
        tag = str(value or "").strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        lowered = tag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        hashtags.append(tag)
        if len(hashtags) == 5:
            break
    return hashtags


def _read_short_metadata(video_path):
    metadata_path = os.path.splitext(video_path)[0] + ".json"
    if not os.path.exists(metadata_path):
        return {}
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {}

    hashtags = _normalize_short_hashtags(payload.get("hashtags"))
    return {
        "caption": str(payload.get("caption", "")).strip(),
        "hashtags": hashtags,
        "hashtags_text": " ".join(hashtags),
        "news_title": str(payload.get("news_title", "")).strip(),
        "script": str(payload.get("script", "")).strip(),
    }

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
CONTROL_FILE = os.path.join(RUNTIME_DIR, "control.txt")
HOUR_CHIME_JINGLE_FILE = os.path.join(BASE_DIR, "assets", "jingles", "jingle_ora_esatta.mp3")
HOUR_CHIME_OUTPUT_FILE = os.path.join(TMP_DIR, "hourly_chime.wav")
HOUR_CHIME_VOICE_FILE = os.path.join(TMP_DIR, "hourly_chime_voice.wav")
FFMPEG_CMD = resolve_ffmpeg_cmd()
ACE_STEP_PYTHON = resolve_ace_step_python()
PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python3")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = os.path.join(BASE_DIR, "venv", "bin", "python")
if not os.path.exists(PYTHON_EXEC):
    PYTHON_EXEC = "python3"

SERVICES = {
    "director": {
        "label": "Regia",
        "patterns": [
            r"src/watchdog\.sh",
            r"src/director\.py",
            r"src/ticker_agent\.py",
            r"src/overlay_agent\.py",
            r"src/hourly_chime_agent\.py",
            r"src/breaking_news_agent\.py",
            r"src/chat_agent\.py",
        ],
        "command": ["bash", os.path.join(BASE_DIR, "src", "watchdog.sh")],
        "log": os.path.join(TMP_DIR, "director.log"),
    },
    "stream": {
        "label": "Stream",
        "patterns": [r"src/stream\.sh", r"ffmpeg.*rtmp://a\.rtmp\.youtube\.com/live2"],
        "command": ["bash", os.path.join(BASE_DIR, "src", "stream.sh")],
        "log": os.path.join(TMP_DIR, "stream.log"),
    },
    "chat_agent": {
        "label": "YouTube Chat",
        "patterns": [r"src/chat_agent\.py"],
        "command": [PYTHON_EXEC, "-u", os.path.join(BASE_DIR, "src", "chat_agent.py")],
        "log": os.path.join(TMP_DIR, "chat_agent.log"),
    },
    "ai_music_worker": {
        "label": "Musica AI Worker",
        "patterns": [r"src/newsica/audio/ai_music_worker\.py"],
        "command": [ACE_STEP_PYTHON, "-u", os.path.join(BASE_DIR, "src", "newsica", "audio", "ai_music_worker.py")],
        "log": os.path.join(TMP_DIR, "ai_music_worker.log"),
    },
    "telegram_agent": {
        "label": "Telegram Bot",
        "patterns": [r"src/telegram_agent\.py"],
        "command": [PYTHON_EXEC, "-u", os.path.join(BASE_DIR, "src", "telegram_agent.py")],
        "log": os.path.join(TMP_DIR, "telegram_agent.log"),
    },
}

MANUAL_EVENT_ORDER = (
    "news",
    "flash_60s",
    "sport",
    "meteo",
    "wellness",
    "podcast",
    "breaking_news",
)

MANUAL_EVENT_META = {
    "news": {
        "label": "TG Newsica",
        "description": "Notiziario generalista o tematico con Chiara.",
        "default_title": "TG Newsica - Edizione Speciale",
        "title_placeholder": "Titolo editoriale opzionale",
        "brief_placeholder": "Lascia vuoto per usare le news del momento oppure descrivi un focus specifico...",
        "requires_brief": False,
    },
    "flash_60s": {
        "label": "Flash 60 Secondi",
        "description": "Bollettino rapidissimo da circa 60 secondi.",
        "default_title": "Flash 60 Secondi",
        "title_placeholder": "Titolo del flash opzionale",
        "brief_placeholder": "Focus opzionale per il flash: mondo, tecnologia, politica, cronaca...",
        "requires_brief": False,
    },
    "sport": {
        "label": "Sport Flash",
        "description": "Aggiornamento sportivo rapido con Leo.",
        "default_title": "Sport Flash",
        "title_placeholder": "Titolo della rubrica sportiva",
        "brief_placeholder": "Focus opzionale: Serie A, Champions, tennis, motori...",
        "requires_brief": False,
    },
    "meteo": {
        "label": "Meteo Update",
        "description": "Bollettino meteo breve e diretto.",
        "default_title": "Meteo Update",
        "title_placeholder": "Titolo del bollettino meteo",
        "brief_placeholder": "Focus opzionale: weekend, Nord Italia, ondata di caldo...",
        "requires_brief": False,
    },
    "wellness": {
        "label": "Benessere",
        "description": "Rubrica salute e benessere con Maya.",
        "default_title": "Benessere in Movimento",
        "title_placeholder": "Titolo della rubrica wellness",
        "brief_placeholder": "Tema opzionale: postura, sonno, stretching, alimentazione...",
        "requires_brief": False,
    },
    "podcast": {
        "label": "Newsica Podcast",
        "description": "Dialogo a due voci con Giulia e Marco.",
        "default_title": "Newsica Podcast",
        "title_placeholder": "Titolo della puntata opzionale",
        "brief_placeholder": "Tema obbligatorio del podcast: es. il futuro del lavoro remoto...",
        "requires_brief": True,
    },
    "breaking_news": {
        "label": "Edizione Straordinaria",
        "description": "Test del prompt breaking news senza passare dalla pipeline automatica.",
        "default_title": "Edizione Straordinaria",
        "title_placeholder": "Titolo opzionale",
        "brief_placeholder": "Focus opzionale: evento urgente o scenario da simulare...",
        "requires_brief": False,
    },
}


def _truncate_label(value, max_chars=40):
    compact = " ".join((value or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _build_manual_event_formats():
    characters = load_characters()
    formats = []
    for character_id in MANUAL_EVENT_ORDER:
        character = characters.get(character_id)
        meta = MANUAL_EVENT_META.get(character_id)
        if not character or not meta:
            continue
        formats.append({
            "id": character.id,
            "label": meta["label"],
            "description": meta["description"],
            "display_name": character.display_name,
            "format": character.format,
            "default_title": meta["default_title"],
            "title_placeholder": meta["title_placeholder"],
            "brief_placeholder": meta["brief_placeholder"],
            "requires_brief": meta["requires_brief"],
        })
    return formats


def _manual_prompt_payload(character_id, title, brief):
    strategist = ContentStrategistAgent()
    character = get_character(character_id)

    if character_id == "podcast":
        all_news = strategist._collect_news(force_fetch=True)
        filtered_news = filter_items_for_character(all_news, character)
        if not filtered_news:
            filtered_news = fallback_general_news(all_news)
        fallback_script = build_fallback_script(character.id, filtered_news, title=title)
        user_prompt = (
            f"Scrivi un copione per il podcast '{title}' sulla seguente tematica descritta dall'utente:\n\n"
            f"\"{brief}\"\n\n"
            "Rispetta rigorosamente eventuali indicazioni di durata o brevità fornite dall'utente nella tematica. "
            "Se non specificato, sviluppa un dialogo naturale, ricco e ben argomentato con un numero di parole "
            "adeguato alla durata del podcast così come richiesto. Se la durata non è definita dall'utente, "
            "sviluppa un dialogo di circa 450-650 parole, distribuito in un vero scambio tra i due speaker e non "
            "in poche battute sbrigative. Il dialogo deve essere diviso a turni di parola tra Giulia e Marco usando "
            "esattamente i tag [SPEAKER: Giulia] e [SPEAKER: Marco] all'inizio di ogni battuta. IMPORTANTE: "
            "I dialoghi devono essere in lingua italiana, con accenti grafici corretti per la sintesi vocale "
            "(`è`, `perché`, `cioè`, `può`, `più`, `né`, `sì`, `dà`, `lì`, `là`). Per temi tecnologici preferisci "
            "`intelligenza artificiale` o `IA` a `AI`, ed espandi le sigle tecniche alla prima occorrenza."
        )
        return {
            "character_id": character.id,
            "display_name": character.display_name,
            "title": title,
            "intro": "",
            "system_prompt": character.read_prompt(),
            "prompt": user_prompt,
            "fallback_script": fallback_script,
            "voice": character.voice,
            "speed": character.speed,
        }

    if character_id == "news":
        content_data = strategist.prepare_content("news", title=title, force_fetch=True)
        if brief:
            news_text = ""
            try:
                results = strategist.search_internet(brief, num_results=4)
                if results:
                    news_text = "Ecco i dettagli emersi dalla ricerca sul tema:\n\n"
                    for res in results:
                        news_text += f"- {res['title']}: {res['snippet']}\n"
                else:
                    news_text = f"Sviluppa un notiziario incentrato su questo tema: {brief}\n"
            except Exception:
                news_text = f"Sviluppa un notiziario incentrato su questo tema: {brief}\n"
        else:
            news_text = content_data["prompt"]

        content_data["prompt"] = (
            f"{news_text}\n\n"
            "Istruzioni speciali:\n"
            "- Scrivi un copione per Chiara in lingua italiana con accenti grafici corretti.\n"
            "- IMPORTANTE: Non includere MAI tag come [MUSIC_BREAK] o interruzioni musicali.\n"
            "- Il testo deve essere di circa 300-400 parole, diviso in paragrafi per la lettura naturale.\n"
            f"- Titolo della trasmissione: {title}\n"
        )
        content_data["intro"] = ""
        return content_data

    content_data = strategist.prepare_content(character_id, title=title, force_fetch=True)
    if brief:
        content_data["prompt"] += (
            "\n\nINDICAZIONE EDITORIALE AGGIUNTIVA DELL'OPERATORE:\n"
            f"{brief}\n\n"
            "Usa questa indicazione solo se coerente con il titolo e con il format della rubrica."
        )
    return content_data


def _combine_manual_event_audio(generated_files, output_path):
    audio_parts = sorted(
        [
            str(path)
            for path in generated_files
            if os.path.basename(str(path)).startswith("audio_part")
            and str(path).endswith(".wav")
            and os.path.exists(path)
        ]
    )
    if not audio_parts:
        return None

    combined = []
    sample_rate = None
    pause_samples = None
    for idx, part_path in enumerate(audio_parts):
        data, sr = sf.read(part_path, dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        if sample_rate is None:
            sample_rate = sr
            pause_samples = np.zeros(int(sample_rate * 0.3), dtype=np.float32)
        elif sr != sample_rate:
            raise RuntimeError(
                f"Sample rate incoerente tra i segmenti manuali: {sr} != {sample_rate}"
            )
        if idx > 0 and pause_samples is not None:
            combined.append(pause_samples)
        combined.append(data)

    if not combined or sample_rate is None:
        return None

    sf.write(output_path, np.concatenate(combined, axis=0), sample_rate)
    return output_path


def _generate_manual_event(character_id, title, brief):
    total_start = time.perf_counter()
    format_map = {item["id"]: item for item in _build_manual_event_formats()}
    format_meta = format_map.get(character_id)
    if not format_meta:
        return {"status": "ERROR", "message": f"Format non supportato: {character_id}"}, 400

    brief = (brief or "").strip()
    title = (title or "").strip() or format_meta["default_title"]
    if format_meta["requires_brief"] and not brief:
        return {"status": "ERROR", "message": "Questo format richiede un tema o un brief."}, 400

    if character_id == "news" and brief and title == format_meta["default_title"]:
        title = f"TG Newsica: {_truncate_label(brief, max_chars=30)}"
    elif brief and title == format_meta["default_title"]:
        title = f"{format_meta['label']}: {_truncate_label(brief, max_chars=30)}"

    try:
        content_data = _manual_prompt_payload(character_id, title, brief)
        integrator = AIIntegratorAgent(work_dir=TMP_DIR)
        llm_start = time.perf_counter()
        script_text = integrator.generate_script(content_data)
        llm_seconds = time.perf_counter() - llm_start
        if character_id == "news":
            script_text = script_text.replace("[MUSIC_BREAK]", "\n\n")
        tts_start = time.perf_counter()
        generated_files = integrator.generate_audio(script_text, content_data)
        tts_seconds = time.perf_counter() - tts_start
    except subprocess.CalledProcessError as e:
        return {
            "status": "ERROR",
            "message": "Sintesi audio fallita.",
            "details": e.stderr or str(e),
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }, 500
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e),
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }, 500

    audio_file = None
    for path in generated_files:
        if str(path).endswith("audio.wav"):
            audio_file = str(path)
            break
    if not audio_file:
        combined_path = _combine_manual_event_audio(
            generated_files,
            os.path.join(TMP_DIR, "audio.wav"),
        )
        if combined_path:
            audio_file = combined_path
    if not audio_file or not os.path.exists(audio_file):
        return {
            "status": "ERROR",
            "message": "Audio finale non trovato dopo la sintesi.",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }, 500

    cmd = f"PLAY_EVENT_IMMEDIATE|{audio_file}|{title}|{character_id}"
    try:
        with open(CONTROL_FILE, "w", encoding="utf-8") as f:
            f.write(cmd)
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Scrittura comando regia fallita: {e}",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }, 500

    total_seconds = time.perf_counter() - total_start
    return {
        "status": "OK",
        "title": title,
        "character_id": character_id,
        "generation_seconds": round(total_seconds, 1),
        "llm_seconds": round(llm_seconds, 1),
        "tts_seconds": round(tts_seconds, 1),
    }, 200



@app.route('/api/state')
def get_state():
    try:
        schedule_data = get_current_schedule()
        sorted_times = sorted(schedule_data.keys())
        schedule_list = []
        for idx, t in enumerate(sorted_times):
            schedule_list.append({
                "time": t,
                "title": schedule_data[t]["title"],
                "type": schedule_data[t]["type"],
                "index": idx
            })
    except Exception as e:
        print(f"⚠️ Errore caricamento palinsesto: {e}")
        schedule_list = []

    from newsica.broadcast.runtime_state import get_current_state
    state = get_current_state()
    state["schedule"] = schedule_list
    return jsonify(state)

@app.route('/api/command', methods=['POST'])
def send_command():
    data = request.json
    cmd = data.get('command')
    if cmd:
        with open(CONTROL_FILE, "w") as f:
            f.write(cmd)
        return jsonify({"status": "OK", "command": cmd})
    return jsonify({"status": "INVALID"})


@app.route('/api/chime', methods=['POST'])
def trigger_chime():
    """Genera il segnale orario manuale: jingle + voce con ora reale."""
    import sys

    if not os.path.exists(HOUR_CHIME_JINGLE_FILE):
        return jsonify({
            "status": "ERROR",
            "message": f"Jingle ora esatta non trovato: {HOUR_CHIME_JINGLE_FILE}",
        }), 500

    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    try:
        from hourly_chime_agent import build_exact_chime_text, generate_chime_audio
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Import agente fallito: {e}"}), 500

    text = build_exact_chime_text()
    if not generate_chime_audio(text, HOUR_CHIME_VOICE_FILE):
        return jsonify({"status": "ERROR", "message": "Generazione TTS fallita."}), 500

    try:
        subprocess.run([
            FFMPEG_CMD,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", HOUR_CHIME_JINGLE_FILE,
            "-i", HOUR_CHIME_VOICE_FILE,
            "-filter_complex",
            "[0:a]aresample=24000,aformat=channel_layouts=mono[j];"
            "[1:a]aresample=24000,aformat=channel_layouts=mono[v];"
            "[j][v]concat=n=2:v=0:a=1[a]",
            "-map", "[a]",
            "-ar", "24000",
            "-ac", "1",
            HOUR_CHIME_OUTPUT_FILE,
        ], check=True)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Preparazione jingle ora esatta fallita: {e}"}), 500

    cmd = f"HOURLY_CHIME_READY|{HOUR_CHIME_OUTPUT_FILE}|force"
    try:
        with open(CONTROL_FILE, "w") as f:
            f.write(cmd)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": f"Scrittura controllo fallita: {e}"}), 500

    return jsonify({"status": "OK", "text": text})

@app.route('/api/music_gen', methods=['POST'])
def trigger_music_gen():
    """Accoda una generazione musicale AI e assicura il worker persistente."""
    try:
        if not os.path.exists(ACE_STEP_PYTHON):
            return jsonify({"status": "ERROR", "message": "Ambiente ACE-Step non installato. Esegui manage.sh install-ace-step"}), 500

        job, created = enqueue_job(
            job_type="rotation_fill",
            source="dashboard",
            dedupe_key="rotation_fill",
        )
        start_service(SERVICES["ai_music_worker"])

        if created:
            return jsonify({"status": "OK", "message": f"Job musica AI accodato ({job['id']})."})
        return jsonify({"status": "OK", "message": f"Worker già impegnato sul job {job['id']}."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def music_mode_payload(status="OK", warning=None):
    mode = read_music_mode()
    counts = MusicLibrary().get_counts()
    label = "Solo Musica AI" if mode == MUSIC_MODE_AI_ONLY else "Mix cartella music + Musica AI"
    payload = {
        "status": status,
        "mode": mode,
        "label": label,
        "counts": counts,
    }
    if warning:
        payload["warning"] = warning
    return payload


@app.route("/api/music_mode", methods=["GET", "POST"])
def api_music_mode():
    if request.method == "POST":
        data = request.json or {}
        mode = data.get("mode")
        if mode not in {MUSIC_MODE_MIXED, MUSIC_MODE_AI_ONLY}:
            return jsonify({
                "status": "ERROR",
                "message": "Modalità non valida. Usa 'mixed' oppure 'ai_only'.",
            }), 400

        write_music_mode(mode)
        counts = MusicLibrary().get_counts()
        warning = None
        if mode == MUSIC_MODE_AI_ONLY and counts.get("ai", 0) == 0:
            warning = "Modalità solo AI attiva, ma assets/ai_music non contiene brani riproducibili."
        return jsonify(music_mode_payload(warning=warning))

    return jsonify(music_mode_payload())


@app.route("/api/audit-log", methods=["GET"])
def api_audit_log():
    audit_file = os.path.join(RUNTIME_DIR, "audit_trail.log")
    try:
        if not os.path.exists(audit_file):
            return jsonify({"lines": ["L'Audit Log è attualmente vuoto o in attesa di dati..."]})
        
        with open(audit_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Ritorniamo le ultime 100 righe, in ordine inverso (le più recenti in alto)
        recent_lines = [line.strip() for line in lines[-100:] if line.strip()]
        return jsonify({"lines": list(reversed(recent_lines))})
    except Exception as e:
        return jsonify({"lines": [f"Errore caricamento log: {str(e)}"]})


@app.route('/api/manual-event-formats')
def get_manual_event_formats():
    return jsonify({"formats": _build_manual_event_formats()})


@app.route('/api/manual-event', methods=['POST'])
def trigger_manual_event():
    data = request.json or {}
    payload, status_code = _generate_manual_event(
        character_id=(data.get("character_id") or "").strip(),
        title=data.get("title", ""),
        brief=data.get("brief", ""),
    )
    return jsonify(payload), status_code

@app.route('/api/podcast', methods=['POST'])
def trigger_podcast():
    """Genera il copione del podcast via Ollama, lo sintetizza e lo manda in onda."""
    total_start = time.perf_counter()
    data = request.json or {}
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"status": "ERROR", "message": "Nessuna tematica fornita."}), 400

    # 1. Carica il prompt di sistema
    prompt_path = os.path.join(BASE_DIR, "src", "newsica", "editorial", "prompts", "podcast.md")
    system_prompt = ""
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as pf:
                system_prompt = pf.read()
        except Exception as e:
            print(f"⚠️ Impossibile leggere il prompt del podcast: {e}")
    
    if not system_prompt:
        system_prompt = "Sei un duo di conduttori radiofonici e podcaster professionisti di NewsicaTV. Genera un copione per una rubrica stile podcast in formato dialogo a due voci Giulia e Marco."

    # 2. Prepara il prompt per Ollama
    user_prompt = f"Scrivi un copione per il podcast 'Newsica Podcast' sulla seguente tematica descritta dall'utente:\n\n\"{topic}\"\n\nRispetta rigorosamente eventuali indicazioni di durata o brevità fornite dall'utente nella tematica. Se non specificato, sviluppa un dialogo naturale, ricco e ben argomentato con un numero di parole adeguato alla durata del podcast così come richiesto. Se la durata non è definita dall'utente, sviluppa un dialogo di circa 450-650 parole, distribuito in un vero scambio tra i due speaker e non in poche battute sbrigative. Il dialogo deve essere diviso a turni di parola tra Giulia e Marco usando esattamente i tag [SPEAKER: Giulia] e [SPEAKER: Marco] all'inizio di ogni battuta. IMPORTANTE: I dialoghi devono essere in lingua italiana, con accenti grafici corretti per la sintesi vocale (`è`, `perché`, `cioè`, `può`, `più`, `né`, `sì`, `dà`, `lì`, `là`). Per temi tecnologici preferisci `intelligenza artificiale` o `IA` a `AI`, ed espandi le sigle tecniche alla prima occorrenza."

    # 3. Interroga Ollama locale
    import requests
    ollama_url = "http://localhost:11434/api/generate"
    model_name = os.getenv("OLLAMA_MODEL", "gemma3:12b")
    
    payload = {
        "model": model_name,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.5,
            "num_predict": 900,
        },
    }

    script_text = ""
    llm_start = time.perf_counter()
    try:
        response = requests.post(ollama_url, json=payload, timeout=60)
        response.raise_for_status()
        script_text = response.json().get("response", "").strip()
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": f"Errore di connessione a Ollama: {e}",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500
    llm_seconds = time.perf_counter() - llm_start

    if not script_text:
        return jsonify({
            "status": "ERROR",
            "message": "Ollama ha restituito un copione vuoto.",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500

    # 4. Scrivi il copione in tmp/script.txt
    script_file = os.path.join(TMP_DIR, "script.txt")
    try:
        with open(script_file, "w", encoding="utf-8") as sf:
            sf.write(script_text)
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": f"Scrittura copione fallita: {e}",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500

    # 5. Genera l'audio via tts_generator.py podcast
    tts_start = time.perf_counter()
    try:
        subprocess.run(
            [PYTHON_EXEC, os.path.join(BASE_DIR, "src", "tts_generator.py"), "podcast"],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        return jsonify({
            "status": "ERROR", 
            "message": "Sintesi audio fallita.", 
            "details": e.stderr,
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500
    tts_seconds = time.perf_counter() - tts_start

    podcast_audio_file = os.path.join(TMP_DIR, "audio.wav")
    if not os.path.exists(podcast_audio_file):
        return jsonify({
            "status": "ERROR",
            "message": "Audio del podcast non trovato dopo la sintesi.",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500

    # 6. Estrai una versione corta del titolo
    short_title = topic[:30] + "..." if len(topic) > 30 else topic
    pod_display_title = f"Newsica Podcast: {short_title}"

    # 7. Invia comando alla regia
    cmd = f"PLAY_PODCAST_IMMEDIATE|{podcast_audio_file}|{pod_display_title}"
    try:
        with open(CONTROL_FILE, "w") as f:
            f.write(cmd)
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": f"Scrittura comando regia fallita: {e}",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500

    total_seconds = time.perf_counter() - total_start
    return jsonify({
        "status": "OK",
        "title": pod_display_title,
        "generation_seconds": round(total_seconds, 1),
        "llm_seconds": round(llm_seconds, 1),
        "tts_seconds": round(tts_seconds, 1),
    })

@app.route('/api/generate_short', methods=['POST'])
def generate_short():
    import sys
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    try:
        from newsica.agents.shorts_agent import ShortsAgent
        agent = ShortsAgent()
        result = agent.run()
        if result.get("status") == "success":
            output_file = result.get("output", "")
            filename = os.path.basename(output_file) if output_file else ""
            result["filename"] = filename
            result["video_url"] = f"/api/shorts_video/{filename}" if filename else ""
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/shorts_library', methods=['GET'])
def shorts_library():
    import glob
    from datetime import datetime
    import re
    shorts_dir = os.path.join(BASE_DIR, "output", "shorts")
    if not os.path.exists(shorts_dir):
        return jsonify({"shorts": []})
        
    shorts = []
    for filepath in glob.glob(os.path.join(shorts_dir, "*.mp4")):
        filename = os.path.basename(filepath)
        
        match = re.search(r'short_(\d{8})_(\d{6})', filename)
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            try:
                dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
            except:
                dt = datetime.fromtimestamp(os.path.getmtime(filepath))
        else:
            dt = datetime.fromtimestamp(os.path.getmtime(filepath))
            
        metadata = _read_short_metadata(filepath)
        shorts.append({
            "filename": filename,
            "url": f"/api/shorts_video/{filename}",
            "timestamp": dt.isoformat(),
            "date_display": dt.strftime("%d/%m/%Y"),
            "time_display": dt.strftime("%H:%M"),
            "caption": metadata.get("caption", ""),
            "hashtags": metadata.get("hashtags", []),
            "hashtags_text": metadata.get("hashtags_text", ""),
            "news_title": metadata.get("news_title", ""),
            "script": metadata.get("script", ""),
        })
        
    shorts.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify({"shorts": shorts})

@app.route('/api/shorts_video/<path:filename>')
def serve_short_video(filename):
    shorts_dir = os.path.join(BASE_DIR, "output", "shorts")
    return send_from_directory(shorts_dir, filename)

@app.route('/api/news', methods=['POST'])
def trigger_news():
    """Genera il notiziario Chiara via Ollama, lo sintetizza e lo manda in onda."""
    total_start = time.perf_counter()
    data = request.json or {}
    topic = data.get("topic", "").strip()

    # 1. Carica il prompt di sistema di Chiara (news.md)
    prompt_path = os.path.join(BASE_DIR, "src", "newsica", "editorial", "prompts", "news.md")
    system_prompt = ""
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as pf:
                system_prompt = pf.read()
        except Exception as e:
            print(f"⚠️ Impossibile leggere il prompt delle news: {e}")
    
    if not system_prompt:
        system_prompt = "Sei Chiara, la conduttrice di NewsicaTV. Genera un notiziario fluido e professionale."

    # 2. Raccoglie notizie in base alla presenza di un topic
    news_text = ""
    title = "TG Newsica - Edizione Straordinaria"
    if topic:
        title = f"TG Newsica: {topic[:30] + '...' if len(topic) > 30 else topic}"
        # Ricerca web opzionale per il topic
        from newsica.agents.content_strategist import ContentStrategistAgent
        try:
            strategist = ContentStrategistAgent()
            results = strategist.search_internet(topic, num_results=4)
            if results:
                news_text = "Ecco i dettagli emersi dalla ricerca sul tema:\n\n"
                for idx, res in enumerate(results):
                    news_text += f"- {res['title']}: {res['snippet']}\n"
            else:
                news_text = f"Sviluppa un notiziario incentrato su questo tema: {topic}\n"
        except Exception as e:
            news_text = f"Sviluppa un notiziario incentrato su questo tema: {topic}\n"
    else:
        # Recupera news di default dall'RSS
        from newsica.agents.content_strategist import ContentStrategistAgent
        try:
            strategist = ContentStrategistAgent()
            news_items = strategist._collect_news(force_fetch=True)
            news_text = "Ecco le ultime notizie dell'ora da sintetizzare:\n\n"
            for item in news_items[:5]:
                news_text += f"- {item.get('title', '')}: {item.get('summary', '')}\n"
        except Exception as e:
            news_text = "Sviluppa un notiziario generale con aggiornamenti dell'ultima ora."

    # 3. Prepara il prompt per Ollama
    user_prompt = f"""
{news_text}

Istruzioni speciali:
- Scrivi un copione per Chiara in lingua italiana con accenti grafici corretti.
- IMPORTANTE: Non includere MAI tag come [MUSIC_BREAK] o interruzioni musicali. Sviluppa un discorso continuo, fluido e professionale da notiziario televisivo.
- Il testo deve essere di circa 300-400 parole, diviso in paragrafi per la lettura naturale.
- Titolo della trasmissione: {title}
"""

    # 4. Interroga Ollama
    import requests
    ollama_url = "http://localhost:11434/api/generate"
    model_name = os.getenv("OLLAMA_MODEL", "gemma3:12b")
    
    payload = {
        "model": model_name,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.4,
            "num_predict": 700,
        },
    }

    script_text = ""
    llm_start = time.perf_counter()
    try:
        response = requests.post(ollama_url, json=payload, timeout=60)
        response.raise_for_status()
        script_text = response.json().get("response", "").strip()
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": f"Errore di connessione a Ollama: {e}",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500
    llm_seconds = time.perf_counter() - llm_start

    if not script_text:
        return jsonify({
            "status": "ERROR",
            "message": "Ollama ha restituito un copione news vuoto.",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500

    # Rimuoviamo eventuali tag [MUSIC_BREAK] spuri se generati per errore dall'LLM
    script_text = script_text.replace("[MUSIC_BREAK]", "\n\n")

    # 5. Scrivi il copione in tmp/script.txt
    script_file = os.path.join(TMP_DIR, "script.txt")
    try:
        with open(script_file, "w", encoding="utf-8") as sf:
            sf.write(script_text)
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": f"Scrittura copione fallita: {e}",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500

    # 6. Genera l'audio via tts_generator.py per Chiara (news)
    tts_start = time.perf_counter()
    try:
        subprocess.run(
            [PYTHON_EXEC, os.path.join(BASE_DIR, "src", "tts_generator.py"), "news"],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        return jsonify({
            "status": "ERROR", 
            "message": "Sintesi audio delle news fallita.", 
            "details": e.stderr,
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500
    tts_seconds = time.perf_counter() - tts_start

    news_audio_file = os.path.join(TMP_DIR, "audio.wav")
    if not os.path.exists(news_audio_file):
        return jsonify({
            "status": "ERROR",
            "message": "Audio delle news non trovato dopo la sintesi.",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500

    # 7. Invia comando alla regia
    cmd = f"PLAY_NEWS_IMMEDIATE|{news_audio_file}|{title}"
    try:
        with open(CONTROL_FILE, "w") as f:
            f.write(cmd)
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": f"Scrittura comando regia fallita: {e}",
            "elapsed_seconds": round(time.perf_counter() - total_start, 1),
        }), 500

    total_seconds = time.perf_counter() - total_start
    return jsonify({
        "status": "OK",
        "title": title,
        "generation_seconds": round(total_seconds, 1),
        "llm_seconds": round(llm_seconds, 1),
        "tts_seconds": round(tts_seconds, 1),
    })

def find_pids(patterns):
    pids = set()
    for pattern in patterns:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid != os.getpid():
                pids.add(pid)
    return sorted(pids)

def terminate_pids(pids):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    deadline = time.time() + 5
    while time.time() < deadline:
        if not any(process_exists(pid) for pid in pids):
            return
        time.sleep(0.2)

    for pid in pids:
        if process_exists(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

def process_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

def start_service(service):
    os.makedirs(TMP_DIR, exist_ok=True)
    log_file = open(service["log"], "a")
    subprocess.Popen(
        service["command"],
        cwd=BASE_DIR,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )

def restart_service(name):
    service = SERVICES[name]
    pids = find_pids(service["patterns"])
    terminate_pids(pids)
    start_service(service)
    return pids

@app.route('/api/service/restart', methods=['POST'])
def restart_service_route():
    data = request.json or {}
    requested_service = data.get("service")

    if requested_service == "all":
        restarted = {}
        for service_name in ("director", "stream", "ai_music_worker"):
            restarted[service_name] = restart_service(service_name)
        return jsonify({
            "status": "OK",
            "message": "servizi riavviati",
            "restarted": restarted,
        })

    if requested_service not in SERVICES:
        return jsonify({"status": "INVALID", "message": "servizio non valido"}), 400

    pids = restart_service(requested_service)
    return jsonify({
        "status": "OK",
        "message": f"{SERVICES[requested_service]['label']} riavviato",
        "restarted_pids": pids,
    })

@app.route('/api/chat/status', methods=['GET'])
def get_chat_status():
    video_id = ""
    for file_name in ("live_video_id.txt", "live_video_cache.txt"):
        file_path = os.path.join(TMP_DIR, file_name)
        if not os.path.exists(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if len(value) == 11:
                video_id = value
                break
        except Exception:
            pass
            
    # Check if chat_agent is running
    pids = find_pids([r"src/chat_agent\.py"])
    is_running = len(pids) > 0
    
    return jsonify({
        "status": "OK",
        "video_id": video_id,
        "is_running": is_running
    })

@app.route('/api/chat/video_id', methods=['POST'])
def save_chat_video_id():
    data = request.json or {}
    video_id = data.get("video_id", "").strip()
    
    file_path = os.path.join(TMP_DIR, "live_video_id.txt")
    if not video_id:
        if os.path.exists(file_path):
            os.remove(file_path)
        message = "Auto-discovery ripristinato"
    else:
        if len(video_id) != 11:
            return jsonify({"status": "INVALID", "message": "L'ID video deve essere di 11 caratteri"}), 400
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(video_id)
        message = f"ID video salvato: {video_id}"
        
    return jsonify({"status": "OK", "message": message})

@app.route('/api/chat/mock', methods=['POST'])
def inject_chat_mock():
    data = request.json or {}
    author = data.get("author", "").strip() or "Spettatore"
    message = data.get("message", "").strip() or "Ciao da NewsicaTV! 🚀"
    role = data.get("role", "regular")
    
    is_moderator = role == "moderator"
    is_owner = role == "owner"
    is_sponsor = role == "sponsor"
    
    chat_data = {
        "author": author,
        "message": message,
        "timestamp": time.time(),
        "is_moderator": is_moderator,
        "is_owner": is_owner,
        "is_sponsor": is_sponsor
    }
    
    from newsica.storage.repositories.editorial_memory_repository import set_memory
    import json
    try:
        set_memory("latest_chat", json.dumps(chat_data, ensure_ascii=False))
    except Exception as e:
        print(f"⚠️ Errore db saving chat: {e}")
        
    return jsonify({"status": "OK", "message": f"Messaggio di {author} iniettato"})


# API per la gestione dei Vocali Telegram
@app.route('/api/telegram-voices', methods=['GET'])
def get_telegram_voices():
    from newsica.storage.repositories.telegram_repository import list_voices
    try:
        raw_voices = list_voices()
        status_rank = {
            "pending": 0,
            "approved": 1,
            "playing": 2,
            "played": 3,
            "rejected": 4,
        }
        voices = []
        for voice in raw_voices:
            author_first_name = (voice.get("author_first_name") or "").strip()
            author_username = (voice.get("author_username") or "").strip()
            author = author_first_name or author_username or "Ascoltatore"
            if author_username and author_username != author_first_name:
                author_display = f"{author} (@{author_username})"
            else:
                author_display = author

            item = dict(voice)
            item["author"] = author_display
            item["can_approve"] = item.get("status") == "pending"
            item["can_reject"] = item.get("status") in {"pending", "approved"}
            item["is_playable"] = bool(item.get("converted_path")) and os.path.exists(item.get("converted_path"))
            voices.append(item)

        voices.sort(
            key=lambda item: (
                status_rank.get(item.get("status"), 99),
                item.get("received_at", ""),
            ),
            reverse=False,
        )
        return jsonify({"status": "OK", "voices": voices})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})


@app.route('/api/telegram-voices/approve/<voice_id>', methods=['POST'])
def approve_telegram_voice(voice_id):
    from newsica.storage.repositories.telegram_repository import approve_voice
    try:
        res = approve_voice(voice_id)
        if res:
            return jsonify({"status": "OK", "message": "Vocale approvato"})
        return jsonify({"status": "ERROR", "message": "Vocale non trovato"})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})


@app.route('/api/telegram-voices/reject/<voice_id>', methods=['POST'])
def reject_telegram_voice(voice_id):
    from newsica.storage.repositories.telegram_repository import reject_voice
    try:
        res = reject_voice(voice_id)
        if res:
            return jsonify({"status": "OK", "message": "Vocale rifiutato"})
        return jsonify({"status": "ERROR", "message": "Vocale non trovato"})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})


@app.route('/api/telegram-voices/play/<voice_id>', methods=['GET'])
def play_telegram_voice(voice_id):
    from newsica.storage.repositories.telegram_repository import get_voice
    try:
        voice = get_voice(voice_id)
        if voice and voice.get("converted_path"):
            path = voice["converted_path"]
            if os.path.exists(path):
                return send_file(path, mimetype="audio/wav")
        return jsonify({"status": "ERROR", "message": "File non trovato"}), 404
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500


@app.route('/api/telegram/status', methods=['GET'])
def get_telegram_status():
    pids = find_pids([r"src/telegram_agent\.py"])
    is_running = len(pids) > 0
    return jsonify({
        "status": "OK",
        "is_running": is_running
    })

@app.route('/api/ai_music_jobs', methods=['GET'])
def get_ai_music_jobs():
    from newsica.storage.repositories.ai_music_jobs_repository import list_jobs
    try:
        jobs = list_jobs()
        return jsonify({"status": "OK", "jobs": jobs})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})

@app.route('/api/db/history', methods=['GET'])
def get_db_history():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM broadcast_history 
                ORDER BY id DESC LIMIT 50
            ''')
            rows = [_decorate_history_row(row) for row in cursor.fetchall()]
        return jsonify({"status": "OK", "data": rows})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})

@app.route('/api/db/memory', methods=['GET'])
def get_db_memory():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM editorial_memory 
                ORDER BY id DESC LIMIT 50
            ''')
            rows = []
            for row in cursor.fetchall():
                item = dict(row)
                formatted = _format_memory_value(item.get("value"))
                item["value_pretty"] = formatted["text"]
                item["value_is_json"] = formatted["is_json"]
                item["value_summary"] = formatted["summary"]
                rows.append(item)
        return jsonify({"status": "OK", "data": rows})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})

@app.route('/api/db/assets', methods=['GET'])
def get_db_assets():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM asset_slots 
                ORDER BY slot_time ASC LIMIT 50
            ''')
            rows = [dict(row) for row in cursor.fetchall()]
        return jsonify({"status": "OK", "data": rows})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})

@app.route('/api/db/music-rotation', methods=['GET'])
def get_music_rotation_debug():
    try:
        return jsonify({"status": "OK", "data": _load_rotation_runtime()})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    asset_path = os.path.join(FRONTEND_DIST_DIR, path)
    if path and os.path.exists(asset_path) and os.path.isfile(asset_path):
        return send_from_directory(FRONTEND_DIST_DIR, path)
    return send_from_directory(FRONTEND_DIST_DIR, 'index.html')

_singleton_lock = None

def check_singleton(name):
    import fcntl
    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")
    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        global _singleton_lock
        _singleton_lock = f
        f.write(str(os.getpid()))
        f.flush()
        return True
    except (IOError, OSError):
        print(f"❌ ERRORE: Un'altra istanza di {name} è già in esecuzione!")
        return False

if __name__ == '__main__':
    import sys
    if not check_singleton("dashboard"):
        print("❌ Uscita immediata per prevenire conflitti.")
        sys.exit(1)
        
    print("🚀 Web Dashboard avviata su http://0.0.0.0:5050")
    app.run(host='0.0.0.0', port=5050, debug=False)
