import json
import os
import signal
import subprocess
import time
from pathlib import Path

from flask import jsonify, request, send_file
from werkzeug.utils import secure_filename

from newsica.generation.artifacts import (
    cleanup_incoming_artifacts,
    publish_ai_music_artifact,
    publish_slot_audio_artifact,
    runtime_assets_dir,
    validate_slot_audio_artifact,
)
from newsica.storage.repositories.ai_music_jobs_repository import enqueue_job
from newsica.storage.repositories.generation_jobs_repository import list_jobs as list_generation_jobs
from newsica.storage.repositories import generation_jobs_repository


def _find_pids(patterns):
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


def _process_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _terminate_pids(pids):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    deadline = time.time() + 5
    while time.time() < deadline:
        if not any(_process_exists(pid) for pid in pids):
            return
        time.sleep(0.2)

    for pid in pids:
        if _process_exists(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def _start_service(service, *, base_dir, tmp_dir):
    os.makedirs(tmp_dir, exist_ok=True)
    log_file = open(service["log"], "a")
    subprocess.Popen(
        service["command"],
        cwd=base_dir,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def _restart_service(name, services, *, base_dir, tmp_dir):
    service = services[name]
    pids = _find_pids(service["patterns"])
    _terminate_pids(pids)
    _start_service(service, base_dir=base_dir, tmp_dir=tmp_dir)
    return pids


def _generation_api_authorized():
    expected = os.getenv("NEWSICA_REMOTE_GENERATION_TOKEN", "").strip()
    if not expected:
        return False, ("NEWSICA_REMOTE_GENERATION_TOKEN non configurato", 503)
    auth_header = request.headers.get("Authorization", "")
    bearer = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
    token = request.headers.get("X-Newsica-Generation-Token", "").strip() or bearer
    if token != expected:
        return False, ("token generazione remoto non valido", 401)
    return True, None


def _require_generation_api_token():
    ok, error = _generation_api_authorized()
    if ok:
        return None
    message, status_code = error
    return jsonify({"status": "ERROR", "message": message}), status_code


def register_system_routes(app, *, base_dir, tmp_dir, services, ace_step_python):
    max_upload_mb = int(os.getenv("NEWSICA_REMOTE_MAX_UPLOAD_MB", "512"))
    app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024

    @app.route('/api/music_gen', methods=['POST'])
    def trigger_music_gen():
        """Accoda una generazione musicale AI e assicura il worker persistente."""
        try:
            if not os.path.exists(ace_step_python):
                return jsonify({"status": "ERROR", "message": "Ambiente ACE-Step non installato. Esegui manage.sh install-ace-step"}), 500

            job, created = enqueue_job(
                job_type="rotation_fill",
                source="dashboard",
                dedupe_key="rotation_fill",
            )
            _start_service(services["ai_music_worker"], base_dir=base_dir, tmp_dir=tmp_dir)

            if created:
                return jsonify({"status": "OK", "message": f"Job musica AI accodato ({job['id']})."})
            return jsonify({"status": "OK", "message": f"Worker già impegnato sul job {job['id']}."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/generation/jobs', methods=['GET'])
    def get_generation_jobs():
        try:
            status = request.args.get("status") or None
            limit = int(request.args.get("limit", "50"))
            limit = max(1, min(limit, 200))
            return jsonify({
                "status": "OK",
                "jobs": list_generation_jobs(status=status, limit=limit),
            })
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)}), 500

    @app.route('/api/generation/summary', methods=['GET'])
    def get_generation_summary():
        try:
            return jsonify({
                "status": "OK",
                "summary": generation_jobs_repository.get_summary(),
                "max_upload_mb": int(app.config.get("MAX_CONTENT_LENGTH", 0) / 1024 / 1024),
            })
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)}), 500

    @app.route('/api/generation/incoming/cleanup', methods=['POST'])
    def cleanup_generation_incoming():
        auth_error = _require_generation_api_token()
        if auth_error:
            return auth_error
        older_than_seconds = int(
            (request.json or {}).get(
                "older_than_seconds",
                os.getenv("NEWSICA_REMOTE_INCOMING_RETENTION_SECONDS", "86400"),
            )
        )
        removed = cleanup_incoming_artifacts(older_than_seconds=older_than_seconds)
        return jsonify({"status": "OK", "removed": removed})

    @app.route('/api/generation/jobs/claim', methods=['POST'])
    def claim_generation_job():
        auth_error = _require_generation_api_token()
        if auth_error:
            return auth_error
        data = request.json or {}
        worker_id = str(data.get("worker_id") or "").strip()
        if not worker_id:
            return jsonify({"status": "INVALID", "message": "worker_id richiesto"}), 400
        job_types = data.get("job_types")
        if job_types is not None and not isinstance(job_types, list):
            return jsonify({"status": "INVALID", "message": "job_types deve essere una lista"}), 400
        job = generation_jobs_repository.claim_next_job(worker_id, job_types=job_types)
        return jsonify({"status": "OK", "job": job})

    @app.route('/api/generation/jobs/<job_id>/running', methods=['POST'])
    def mark_generation_job_running(job_id):
        auth_error = _require_generation_api_token()
        if auth_error:
            return auth_error
        worker_id = str((request.json or {}).get("worker_id") or "").strip()
        if not worker_id:
            return jsonify({"status": "INVALID", "message": "worker_id richiesto"}), 400
        return jsonify({"status": "OK", "job": generation_jobs_repository.mark_running(job_id, worker_id)})

    @app.route('/api/generation/jobs/<job_id>/heartbeat', methods=['POST'])
    def heartbeat_generation_job(job_id):
        auth_error = _require_generation_api_token()
        if auth_error:
            return auth_error
        worker_id = str((request.json or {}).get("worker_id") or "").strip()
        if not worker_id:
            return jsonify({"status": "INVALID", "message": "worker_id richiesto"}), 400
        return jsonify({"status": "OK", "job": generation_jobs_repository.heartbeat(job_id, worker_id)})

    @app.route('/api/generation/jobs/<job_id>/uploading', methods=['POST'])
    def mark_generation_job_uploading(job_id):
        auth_error = _require_generation_api_token()
        if auth_error:
            return auth_error
        data = request.json or {}
        worker_id = str(data.get("worker_id") or "").strip()
        if not worker_id:
            return jsonify({"status": "INVALID", "message": "worker_id richiesto"}), 400
        return jsonify({
            "status": "OK",
            "job": generation_jobs_repository.mark_uploading(
                job_id,
                worker_id,
                artifact_manifest=data.get("artifact_manifest"),
            ),
        })

    @app.route('/api/generation/jobs/<job_id>/artifact', methods=['POST'])
    def upload_generation_job_artifact(job_id):
        auth_error = _require_generation_api_token()
        if auth_error:
            return auth_error
        worker_id = str(request.form.get("worker_id") or "").strip()
        if not worker_id:
            return jsonify({"status": "INVALID", "message": "worker_id richiesto"}), 400
        job = generation_jobs_repository.get_job(job_id)
        if not job:
            return jsonify({"status": "ERROR", "message": "job non trovato"}), 404
        if job.get("worker_id") != worker_id:
            return jsonify({"status": "ERROR", "message": "worker non proprietario del job"}), 409

        try:
            manifest = json.loads(request.form.get("manifest_json") or "{}")
        except Exception as e:
            return jsonify({"status": "INVALID", "message": f"manifest_json non valido: {e}"}), 400

        incoming_dir = runtime_assets_dir() / "incoming" / job_id
        incoming_dir.mkdir(parents=True, exist_ok=True)
        (incoming_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for uploaded_file in request.files.getlist("files"):
            filename = secure_filename(uploaded_file.filename or "")
            if not filename:
                continue
            uploaded_file.save(incoming_dir / filename)

        if job.get("job_type") == "slot_audio":
            expected = {
                "slot_time": job.get("slot_time"),
                "character": job.get("character"),
                "title": job.get("title"),
            }
            validated_manifest = validate_slot_audio_artifact(incoming_dir, expected)
            ready_dir = publish_slot_audio_artifact(
                incoming_dir,
                job.get("slot_time") or validated_manifest.get("slot_time"),
            )
            artifact_manifest = dict(validated_manifest)
            artifact_manifest["ready_dir"] = str(ready_dir)
        elif job.get("job_type") == "ai_music":
            target_audio = publish_ai_music_artifact(incoming_dir)
            artifact_manifest = dict(manifest)
            artifact_manifest["audio_path"] = str(target_audio)
            artifact_manifest["audio_file"] = target_audio.name
        else:
            return jsonify({"status": "INVALID", "message": f"job_type non supportato: {job.get('job_type')}"}), 400

        return jsonify({"status": "OK", "artifact_manifest": artifact_manifest})

    @app.route('/api/generation/jobs/<job_id>/ready', methods=['POST'])
    def mark_generation_job_ready(job_id):
        auth_error = _require_generation_api_token()
        if auth_error:
            return auth_error
        data = request.json or {}
        worker_id = str(data.get("worker_id") or "").strip()
        if not worker_id:
            return jsonify({"status": "INVALID", "message": "worker_id richiesto"}), 400
        return jsonify({
            "status": "OK",
            "job": generation_jobs_repository.mark_ready(
                job_id,
                worker_id,
                artifact_manifest=data.get("artifact_manifest"),
            ),
        })

    @app.route('/api/generation/jobs/<job_id>/failed', methods=['POST'])
    def mark_generation_job_failed(job_id):
        auth_error = _require_generation_api_token()
        if auth_error:
            return auth_error
        data = request.json or {}
        worker_id = str(data.get("worker_id") or "").strip()
        if not worker_id:
            return jsonify({"status": "INVALID", "message": "worker_id richiesto"}), 400
        return jsonify({
            "status": "OK",
            "job": generation_jobs_repository.mark_failed(
                job_id,
                worker_id,
                data.get("error") or "errore remoto non specificato",
            ),
        })

    @app.route('/api/service/restart', methods=['POST'])
    def restart_service_route():
        data = request.json or {}
        requested_service = data.get("service")

        if requested_service == "all":
            restarted = {}
            for service_name in ("director", "stream", "ai_music_worker"):
                restarted[service_name] = _restart_service(service_name, services, base_dir=base_dir, tmp_dir=tmp_dir)
            return jsonify({
                "status": "OK",
                "message": "servizi riavviati",
                "restarted": restarted,
            })

        if requested_service not in services:
            return jsonify({"status": "INVALID", "message": "servizio non valido"}), 400

        pids = _restart_service(requested_service, services, base_dir=base_dir, tmp_dir=tmp_dir)
        return jsonify({
            "status": "OK",
            "message": f"{services[requested_service]['label']} riavviato",
            "restarted_pids": pids,
        })

    @app.route('/api/chat/status', methods=['GET'])
    def get_chat_status():
        video_id = ""
        for file_name in ("live_video_id.txt", "live_video_cache.txt"):
            file_path = os.path.join(tmp_dir, file_name)
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

        pids = _find_pids([r"src/chat_agent\.py"])
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

        file_path = os.path.join(tmp_dir, "live_video_id.txt")
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

        chat_data = {
            "author": author,
            "message": message,
            "timestamp": time.time(),
            "is_moderator": role == "moderator",
            "is_owner": role == "owner",
            "is_sponsor": role == "sponsor"
        }

        from newsica.storage.repositories.editorial_memory_repository import set_memory
        try:
            set_memory("latest_chat", json.dumps(chat_data, ensure_ascii=False))
        except Exception as e:
            print(f"⚠️ Errore db saving chat: {e}")

        return jsonify({"status": "OK", "message": f"Messaggio di {author} iniettato"})

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
        pids = _find_pids([r"src/telegram_agent\.py"])
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

    @app.route('/api/ai_music_jobs/claim', methods=['POST'])
    def claim_ai_music_job():
        from newsica.storage.repositories.ai_music_jobs_repository import get_next_pending_job
        try:
            job = get_next_pending_job()
            return jsonify({"status": "OK", "job": job})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)}), 500

    @app.route('/api/ai_music_jobs/<job_id>/running', methods=['POST'])
    def ai_music_job_running(job_id):
        from newsica.storage.repositories.ai_music_jobs_repository import mark_running
        try:
            job = mark_running(job_id)
            return jsonify({"status": "OK", "job": job})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)}), 500

    @app.route('/api/ai_music_jobs/<job_id>/failed', methods=['POST'])
    def ai_music_job_failed(job_id):
        from newsica.storage.repositories.ai_music_jobs_repository import mark_failed
        try:
            data = request.json or {}
            error = data.get("error") or "errore remoto"
            job = mark_failed(job_id, error)
            return jsonify({"status": "OK", "job": job})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)}), 500

    @app.route('/api/ai_music_jobs/<job_id>/artifact', methods=['POST'])
    def ai_music_job_artifact(job_id):
        from newsica.storage.repositories.ai_music_jobs_repository import mark_done, get_job_by_id
        from newsica.storage.repositories.chat_music_requests_repository import mark_ready
        try:
            job = get_job_by_id(job_id)
            if not job:
                return jsonify({"status": "ERROR", "message": "job non trovato"}), 404

            if "file" not in request.files:
                return jsonify({"status": "INVALID", "message": "Nessun file audio inviato"}), 400

            uploaded_file = request.files["file"]
            title = request.form.get("title") or job.get("theme") or "Traccia Generata"

            incoming_dir = runtime_assets_dir() / "incoming" / job_id
            incoming_dir.mkdir(parents=True, exist_ok=True)
            filename = secure_filename(uploaded_file.filename or f"{job_id}.wav")
            temp_path = incoming_dir / filename
            uploaded_file.save(temp_path)

            manifest = {"audio_file": filename}
            (incoming_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            target_audio = publish_ai_music_artifact(incoming_dir)
            updated_job = mark_done(job_id, str(target_audio), title)
            
            request_id = job.get("request_id")
            if request_id:
                mark_ready(request_id, asset_path=str(target_audio), title=title)

            return jsonify({"status": "OK", "job": updated_job, "audio_path": str(target_audio)})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": str(e)}), 500

