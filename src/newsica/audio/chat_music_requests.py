from __future__ import annotations

import json
import time
from pathlib import Path

from newsica.config.paths import RUNTIME_DIR

REQUESTS_FILE = RUNTIME_DIR / "chat_music_requests.json"


def _load_payload(path: Path = REQUESTS_FILE) -> dict:
    if not path.exists():
        return {"requests": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"requests": []}
    if not isinstance(data, dict):
        return {"requests": []}
    requests = data.get("requests")
    if not isinstance(requests, list):
        data["requests"] = []
    return data


def _save_payload(payload: dict, path: Path = REQUESTS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def list_requests(path: Path = REQUESTS_FILE) -> list[dict]:
    return list(_load_payload(path).get("requests", []))


def enqueue_request(
    *,
    author: str,
    message: str,
    theme: str | None,
    custom_brief: str | None,
    path: Path = REQUESTS_FILE,
) -> dict:
    payload = _load_payload(path)
    request_id = f"chatreq_{int(time.time() * 1000)}"
    request = {
        "id": request_id,
        "author": author,
        "message": message,
        "theme": theme,
        "custom_brief": custom_brief,
        "status": "pending",
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    payload["requests"].append(request)
    _save_payload(payload, path)
    return request


def get_next_request_by_status(status: str, path: Path = REQUESTS_FILE) -> dict | None:
    payload = _load_payload(path)
    for request in payload.get("requests", []):
        if request.get("status") == status:
            return dict(request)
    return None


def get_request(request_id: str, path: Path = REQUESTS_FILE) -> dict | None:
    payload = _load_payload(path)
    for request in payload.get("requests", []):
        if request.get("id") == request_id:
            return dict(request)
    return None


def update_request(
    request_id: str,
    *,
    path: Path = REQUESTS_FILE,
    **updates,
) -> dict | None:
    payload = _load_payload(path)
    for request in payload.get("requests", []):
        if request.get("id") != request_id:
            continue
        request.update(updates)
        _save_payload(payload, path)
        return dict(request)
    return None


def mark_generating(request_id: str, path: Path = REQUESTS_FILE) -> dict | None:
    return update_request(
        request_id,
        path=path,
        status="generating",
        generation_started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def mark_ready(
    request_id: str,
    *,
    audio_path: str,
    title: str | None,
    path: Path = REQUESTS_FILE,
) -> dict | None:
    return update_request(
        request_id,
        path=path,
        status="ready",
        ready_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        audio_path=audio_path,
        generated_title=title or "",
    )


def mark_failed(request_id: str, error: str, path: Path = REQUESTS_FILE) -> dict | None:
    return update_request(
        request_id,
        path=path,
        status="failed",
        failed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        error=error[:400],
    )


def consume_next_ready_request(path: Path = REQUESTS_FILE) -> dict | None:
    payload = _load_payload(path)
    for request in payload.get("requests", []):
        if request.get("status") != "ready":
            continue
        request["status"] = "queued_for_playout"
        request["queued_for_playout_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_payload(payload, path)
        return dict(request)
    return None
