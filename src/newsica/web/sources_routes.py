"""API routes per la gestione delle fonti RSS dalla dashboard.

Endpoints:
    GET  /api/sources          → lista tutte le fonti con metadati
    POST /api/sources          → aggiunge o aggiorna una fonte
    DELETE /api/sources/<id>   → rimuove una fonte
    GET  /api/sources/<id>/preview → prime 5 notizie del feed live
"""
import re

import feedparser
import requests
from flask import jsonify, request

from newsica.sources.loader import (
    add_source,
    load_all_sources_detail,
    remove_source,
)


def _is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://", url.strip()))


def _fetch_preview(url: str, max_items: int = 5) -> list[dict]:
    """Recupera le ultime notizie da un feed RSS per l'anteprima."""
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "NewsicaTV/1.0"})
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Impossibile raggiungere il feed: {e}") from e

    parsed = feedparser.parse(resp.content)
    feed_title = getattr(parsed.feed, "title", url)
    items = []
    for entry in parsed.entries[:max_items]:
        items.append({
            "title": getattr(entry, "title", ""),
            "link": getattr(entry, "link", ""),
            "published": getattr(entry, "published", ""),
            "summary": getattr(entry, "summary", "")[:200],
        })
    return {"feed_title": feed_title, "items": items}


def register_sources_routes(app):
    """Registra le route di gestione fonti sull'app Flask."""

    @app.route("/api/sources", methods=["GET"])
    def list_sources():
        try:
            sources = load_all_sources_detail()
            return jsonify({"sources": sources})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/sources", methods=["POST"])
    def add_source_route():
        data = request.json or {}
        feed_id = (data.get("id") or "").strip().lower()
        url = (data.get("url") or "").strip()
        category = (data.get("category") or "general").strip().lower()

        if not feed_id:
            return jsonify({"error": "Il campo 'id' è obbligatorio."}), 400
        if not re.match(r"^[a-z0-9_]+$", feed_id):
            return jsonify({"error": "L'id deve contenere solo lettere minuscole, numeri e underscore."}), 400
        if not url or not _is_valid_url(url):
            return jsonify({"error": "URL non valido. Deve iniziare con http:// o https://"}), 400

        try:
            entry = add_source(feed_id, url, category)
            return jsonify({"status": "ok", "source": {"id": feed_id, **entry}}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/sources/<feed_id>", methods=["DELETE"])
    def delete_source_route(feed_id):
        try:
            removed = remove_source(feed_id)
            if not removed:
                return jsonify({"error": f"Fonte '{feed_id}' non trovata."}), 404
            return jsonify({"status": "ok", "removed": feed_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/sources/<feed_id>/preview", methods=["GET"])
    def preview_source_route(feed_id):
        sources = load_all_sources_detail()
        source = next((s for s in sources if s["id"] == feed_id), None)

        # Fallback: prova con l'url passato direttamente come query param
        url = request.args.get("url") or (source["url"] if source else None)
        if not url:
            return jsonify({"error": f"Fonte '{feed_id}' non trovata."}), 404
        try:
            preview = _fetch_preview(url)
            return jsonify(preview)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 502
