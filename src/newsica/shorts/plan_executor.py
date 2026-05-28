import json
import os

from newsica.shorts.social_service import (
    build_full_caption,
    schedule_short_to_all,
    track_social_posts,
)
from newsica.storage.repositories.shorts_plan_repository import (
    get_pending_generation_items,
    update_item_status,
)


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _find_matching_news_item(title: str, summary: str) -> dict | None:
    normalized_title = _normalize_text(title)
    normalized_summary = _normalize_text(summary)
    if not normalized_title and not normalized_summary:
        return None

    from newsica.agents.content_strategist import ContentStrategistAgent

    strategist = ContentStrategistAgent()
    for force_fetch in (False, True):
        try:
            all_news = strategist._collect_news(force_fetch=force_fetch) or []
        except Exception:
            all_news = []

        for item in all_news:
            item_title = _normalize_text(item.get("title", ""))
            item_summary = _normalize_text(item.get("summary") or item.get("description") or "")
            if normalized_title and item_title == normalized_title:
                return item
            if normalized_summary and item_summary == normalized_summary:
                return item
    return None


def _build_news_payload(item: dict, mode: str) -> dict:
    title = item.get("source_title", "")
    summary = item.get("source_summary", "")
    matched_news_item = _find_matching_news_item(title=title, summary=summary)
    if matched_news_item:
        payload = dict(matched_news_item)
        payload["title"] = payload.get("title") or title
        payload["summary"] = payload.get("summary") or payload.get("description") or summary
        payload["description"] = payload.get("description") or payload.get("summary") or summary
        payload["theme_color"] = mode
        return payload

    return {
        "title": title,
        "summary": summary,
        "description": summary,
        "source": mode,
        "theme_color": mode,
    }


def process_one_planned_short_item(due_within_minutes: int | None = None) -> dict:
    """
    Esegue un solo item del piano shorts in stato `planned`.
    Restituisce un dizionario con `status` e dettaglio esito.
    """
    pending = get_pending_generation_items(limit=1, due_within_minutes=due_within_minutes)
    if not pending:
        return {"status": "idle", "message": "Nessun item shorts pianificato in attesa."}

    from newsica.agents.shorts_agent import ShortsAgent

    item = pending[0]
    item_id = int(item.get("id", 0))
    mode = str(item.get("mode", "news")).strip().lower() or "news"
    due_at_by_platform = item.get("scheduled_for") or {}
    if not item_id:
        return {"status": "error", "message": "Item shorts non valido."}

    update_item_status(item_id, "generating")
    try:
        agent = ShortsAgent()

        # Prova a riallineare l'item pianificato con la news reale per mantenere
        # la provenienza editoriale corretta al momento della pubblicazione.
        news_payload = _build_news_payload(item, mode)

        result = agent.run(mode=mode, news_item=news_payload)
        if result.get("status") != "success":
            update_item_status(item_id, "failed", error=result.get("message", "generazione short fallita"))
            return {"status": "error", "message": result.get("message", "Generazione short fallita."), "item_id": item_id}

        output_file = result.get("output", "")
        filename = os.path.basename(output_file) if output_file else ""
        title = result.get("news_title", "Short NewsicaTV")
        caption = result.get("caption", "")
        hashtags = result.get("hashtags") or []
        full_caption = build_full_caption(caption, hashtags)

        scheduled = schedule_short_to_all(
            video_path=output_file,
            title=title,
            caption=full_caption,
            due_at_by_platform=due_at_by_platform,
        )
        if scheduled.get("status") in {"success", "partial"}:
            track_social_posts(filename, "all", scheduled)
            update_item_status(
                item_id,
                "scheduled",
                short_filename=filename,
                publish_result_json=json.dumps(scheduled, ensure_ascii=False),
            )
            return {
                "status": scheduled.get("status"),
                "message": scheduled.get("message"),
                "item_id": item_id,
                "filename": filename,
            }

        update_item_status(
            item_id,
            "failed",
            short_filename=filename,
            error=scheduled.get("message", "schedulazione social fallita"),
            publish_result_json=json.dumps(scheduled, ensure_ascii=False),
        )
        return {
            "status": "error",
            "message": scheduled.get("message", "Schedulazione social fallita."),
            "item_id": item_id,
            "filename": filename,
        }
    except Exception as e:
        update_item_status(item_id, "failed", error=str(e))
        return {"status": "error", "message": str(e), "item_id": item_id}
