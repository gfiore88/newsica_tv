import os
import subprocess
import time

import numpy as np
import soundfile as sf
from flask import jsonify, request

from newsica.agents.ai_integrator import AIIntegratorAgent
from newsica.agents.content_strategist import ContentStrategistAgent
from newsica.domain.characters import get_character, load_characters
from newsica.editorial.fallback_scripts import build_fallback_script
from newsica.editorial.source_filters import fallback_general_news, filter_items_for_character

MANUAL_EVENT_ORDER = (
    "news",
    "flash_60s",
    "sport",
    "meteo",
    "wellness",
    "motori",
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
    "motori": {
        "label": "Auto & Motori",
        "description": "Rubrica auto e motori con Giorgio.",
        "default_title": "Pista e Strada",
        "title_placeholder": "Titolo della rubrica auto & motori",
        "brief_placeholder": "Tema opzionale: F1, supercar, mobilità sostenibile, novità...",
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
        formats.append(
            {
                "id": character.id,
                "label": meta["label"],
                "description": meta["description"],
                "display_name": character.display_name,
                "format": character.format,
                "default_title": meta["default_title"],
                "title_placeholder": meta["title_placeholder"],
                "brief_placeholder": meta["brief_placeholder"],
                "requires_brief": meta["requires_brief"],
            }
        )
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


def _generate_manual_event(character_id, title, brief, *, tmp_dir, control_file):
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
        integrator = AIIntegratorAgent(work_dir=tmp_dir)
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
            os.path.join(tmp_dir, "audio.wav"),
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
        with open(control_file, "w", encoding="utf-8") as f:
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


def register_editorial_routes(
    app,
    *,
    base_dir,
    tmp_dir,
    control_file,
    ffmpeg_cmd,
    python_exec,
    hour_chime_jingle_file,
    hour_chime_output_file,
    hour_chime_voice_file,
):
    @app.route('/api/chime', methods=['POST'])
    def trigger_chime():
        """Genera il segnale orario manuale: jingle + voce con ora reale."""
        import sys

        if not os.path.exists(hour_chime_jingle_file):
            return jsonify(
                {
                    "status": "ERROR",
                    "message": f"Jingle ora esatta non trovato: {hour_chime_jingle_file}",
                }
            ), 500

        sys.path.insert(0, os.path.join(base_dir, "src"))
        try:
            from hourly_chime_agent import build_exact_chime_text, generate_chime_audio
        except Exception as e:
            return jsonify({"status": "ERROR", "message": f"Import agente fallito: {e}"}), 500

        text = build_exact_chime_text()
        if not generate_chime_audio(text, hour_chime_voice_file):
            return jsonify({"status": "ERROR", "message": "Generazione TTS fallita."}), 500

        try:
            subprocess.run(
                [
                    ffmpeg_cmd,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    hour_chime_jingle_file,
                    "-i",
                    hour_chime_voice_file,
                    "-filter_complex",
                    "[0:a]aresample=24000,aformat=channel_layouts=mono[j];"
                    "[1:a]aresample=24000,aformat=channel_layouts=mono[v];"
                    "[j][v]concat=n=2:v=0:a=1[a]",
                    "-map",
                    "[a]",
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    hour_chime_output_file,
                ],
                check=True,
            )
        except Exception as e:
            return jsonify({"status": "ERROR", "message": f"Preparazione jingle ora esatta fallita: {e}"}), 500

        cmd = f"HOURLY_CHIME_READY|{hour_chime_output_file}|force"
        try:
            with open(control_file, "w", encoding="utf-8") as f:
                f.write(cmd)
        except Exception as e:
            return jsonify({"status": "ERROR", "message": f"Scrittura controllo fallita: {e}"}), 500

        return jsonify({"status": "OK", "text": text})

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
            tmp_dir=tmp_dir,
            control_file=control_file,
        )
        return jsonify(payload), status_code

    @app.route('/api/podcast', methods=['POST'])
    def trigger_podcast():
        total_start = time.perf_counter()
        data = request.json or {}
        topic = data.get("topic", "").strip()
        if not topic:
            return jsonify({"status": "ERROR", "message": "Nessuna tematica fornita."}), 400

        prompt_path = os.path.join(base_dir, "src", "newsica", "editorial", "prompts", "podcast.md")
        system_prompt = ""
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as pf:
                    system_prompt = pf.read()
            except Exception as e:
                print(f"⚠️ Impossibile leggere il prompt del podcast: {e}")
        if not system_prompt:
            system_prompt = "Sei un duo di conduttori radiofonici e podcaster professionisti di NewsicaTV. Genera un copione per una rubrica stile podcast in formato dialogo a due voci Giulia e Marco."

        user_prompt = f"Scrivi un copione per il podcast 'Newsica Podcast' sulla seguente tematica descritta dall'utente:\n\n\"{topic}\"\n\nRispetta rigorosamente eventuali indicazioni di durata o brevità fornite dall'utente nella tematica. Se non specificato, sviluppa un dialogo naturale, ricco e ben argomentato con un numero di parole adeguato alla durata del podcast così come richiesto. Se la durata non è definita dall'utente, sviluppa un dialogo di circa 450-650 parole, distribuito in un vero scambio tra i due speaker e non in poche battute sbrigative. Il dialogo deve essere diviso a turni di parola tra Giulia e Marco usando esattamente i tag [SPEAKER: Giulia] e [SPEAKER: Marco] all'inizio di ogni battuta. IMPORTANTE: I dialoghi devono essere in lingua italiana, con accenti grafici corretti per la sintesi vocale (`è`, `perché`, `cioè`, `può`, `più`, `né`, `sì`, `dà`, `lì`, `là`). Per temi tecnologici preferisci `intelligenza artificiale` o `IA` a `AI`, ed espandi le sigle tecniche alla prima occorrenza."

        import requests

        ollama_url = "http://localhost:11434/api/generate"
        model_name = os.getenv("OLLAMA_MODEL", "gemma3:12b")
        payload = {
            "model": model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.5, "num_predict": 900},
        }

        script_text = ""
        llm_start = time.perf_counter()
        try:
            response = requests.post(ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            script_text = response.json().get("response", "").strip()
        except Exception as e:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": f"Errore di connessione a Ollama: {e}",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500
        llm_seconds = time.perf_counter() - llm_start

        if not script_text:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": "Ollama ha restituito un copione vuoto.",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500

        script_file = os.path.join(tmp_dir, "script.txt")
        try:
            with open(script_file, "w", encoding="utf-8") as sf_file:
                sf_file.write(script_text)
        except Exception as e:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": f"Scrittura copione fallita: {e}",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500

        tts_start = time.perf_counter()
        try:
            subprocess.run(
                [python_exec, os.path.join(base_dir, "src", "tts_generator.py"), "podcast"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": "Sintesi audio fallita.",
                    "details": e.stderr,
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500
        tts_seconds = time.perf_counter() - tts_start

        podcast_audio_file = os.path.join(tmp_dir, "audio.wav")
        if not os.path.exists(podcast_audio_file):
            return jsonify(
                {
                    "status": "ERROR",
                    "message": "Audio del podcast non trovato dopo la sintesi.",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500

        short_title = topic[:30] + "..." if len(topic) > 30 else topic
        pod_display_title = f"Newsica Podcast: {short_title}"
        cmd = f"PLAY_PODCAST_IMMEDIATE|{podcast_audio_file}|{pod_display_title}"
        try:
            with open(control_file, "w", encoding="utf-8") as f:
                f.write(cmd)
        except Exception as e:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": f"Scrittura comando regia fallita: {e}",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500

        total_seconds = time.perf_counter() - total_start
        return jsonify(
            {
                "status": "OK",
                "title": pod_display_title,
                "generation_seconds": round(total_seconds, 1),
                "llm_seconds": round(llm_seconds, 1),
                "tts_seconds": round(tts_seconds, 1),
            }
        )

    @app.route('/api/news', methods=['POST'])
    def trigger_news():
        total_start = time.perf_counter()
        data = request.json or {}
        topic = data.get("topic", "").strip()

        prompt_path = os.path.join(base_dir, "src", "newsica", "editorial", "prompts", "news.md")
        system_prompt = ""
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as pf:
                    system_prompt = pf.read()
            except Exception as e:
                print(f"⚠️ Impossibile leggere il prompt delle news: {e}")
        if not system_prompt:
            system_prompt = "Sei Chiara, la conduttrice di NewsicaTV. Genera un notiziario fluido e professionale."

        news_text = ""
        title = "TG Newsica - Edizione Straordinaria"
        if topic:
            title = f"TG Newsica: {topic[:30] + '...' if len(topic) > 30 else topic}"
            try:
                strategist = ContentStrategistAgent()
                results = strategist.search_internet(topic, num_results=4)
                if results:
                    news_text = "Ecco i dettagli emersi dalla ricerca sul tema:\n\n"
                    for res in results:
                        news_text += f"- {res['title']}: {res['snippet']}\n"
                else:
                    news_text = f"Sviluppa un notiziario incentrato su questo tema: {topic}\n"
            except Exception:
                news_text = f"Sviluppa un notiziario incentrato su questo tema: {topic}\n"
        else:
            try:
                strategist = ContentStrategistAgent()
                news_items = strategist._collect_news(force_fetch=True)
                news_text = "Ecco le ultime notizie dell'ora da sintetizzare:\n\n"
                for item in news_items[:5]:
                    news_text += f"- {item.get('title', '')}: {item.get('summary', '')}\n"
            except Exception:
                news_text = "Sviluppa un notiziario generale con aggiornamenti dell'ultima ora."

        user_prompt = f"""
{news_text}

Istruzioni speciali:
- Scrivi un copione per Chiara in lingua italiana con accenti grafici corretti.
- IMPORTANTE: Non includere MAI tag come [MUSIC_BREAK] o interruzioni musicali. Sviluppa un discorso continuo, fluido e professionale da notiziario televisivo.
- Il testo deve essere di circa 300-400 parole, diviso in paragrafi per la lettura naturale.
- Titolo della trasmissione: {title}
"""

        import requests

        ollama_url = "http://localhost:11434/api/generate"
        model_name = os.getenv("OLLAMA_MODEL", "gemma3:12b")
        payload = {
            "model": model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.4, "num_predict": 700},
        }

        script_text = ""
        llm_start = time.perf_counter()
        try:
            response = requests.post(ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            script_text = response.json().get("response", "").strip()
        except Exception as e:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": f"Errore di connessione a Ollama: {e}",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500
        llm_seconds = time.perf_counter() - llm_start

        if not script_text:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": "Ollama ha restituito un copione news vuoto.",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500

        script_text = script_text.replace("[MUSIC_BREAK]", "\n\n")
        script_file = os.path.join(tmp_dir, "script.txt")
        try:
            with open(script_file, "w", encoding="utf-8") as sf_file:
                sf_file.write(script_text)
        except Exception as e:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": f"Scrittura copione fallita: {e}",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500

        tts_start = time.perf_counter()
        try:
            subprocess.run(
                [python_exec, os.path.join(base_dir, "src", "tts_generator.py"), "news"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": "Sintesi audio delle news fallita.",
                    "details": e.stderr,
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500
        tts_seconds = time.perf_counter() - tts_start

        news_audio_file = os.path.join(tmp_dir, "audio.wav")
        if not os.path.exists(news_audio_file):
            return jsonify(
                {
                    "status": "ERROR",
                    "message": "Audio delle news non trovato dopo la sintesi.",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500

        cmd = f"PLAY_NEWS_IMMEDIATE|{news_audio_file}|{title}"
        try:
            with open(control_file, "w", encoding="utf-8") as f:
                f.write(cmd)
        except Exception as e:
            return jsonify(
                {
                    "status": "ERROR",
                    "message": f"Scrittura comando regia fallita: {e}",
                    "elapsed_seconds": round(time.perf_counter() - total_start, 1),
                }
            ), 500

        total_seconds = time.perf_counter() - total_start
        return jsonify(
            {
                "status": "OK",
                "title": title,
                "generation_seconds": round(total_seconds, 1),
                "llm_seconds": round(llm_seconds, 1),
                "tts_seconds": round(tts_seconds, 1),
            }
        )
