import os
from datetime import datetime, date, time, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from newsica.editorial.gravity_assessor import calculate_heuristic_score, assess_news_gravity
from newsica.storage.repositories.shorts_plan_repository import (
    add_plan_item,
    get_daily_plan,
    list_plan_items,
    save_daily_plan,
    summarize_plan_status,
)

ALWAYS_MODES = ("news", "funfact", "tech")
CONDITIONAL_MODES = ("meteo", "sport", "wellness", "motori")

MODE_SOURCE_MAP = {
    "sport": {"ansa_sport", "agi_sport"},
    "meteo": {"meteo"},
    "tech": {"ansa_tecnologia", "agi_innovazione"},
    "wellness": {"ansa_salute_benessere", "ansa_lifestyle"},
    "motori": {"ansa_motori"},
}

MODE_THRESHOLDS = {
    "meteo": 55,
    "sport": 45,
    "wellness": 45,
    "motori": 45,
}

DEFAULT_HOT_WINDOWS = {
    "instagram": ["12:15", "18:45", "21:15", "22:45"],
    "tiktok": ["12:45", "19:30", "21:45", "23:00"],
    "youtube": ["12:30", "17:45", "20:30", "22:15"],
}


class DailyShortsPlanner:
    def __init__(self):
        self.timezone = os.getenv("SHORTS_TIMEZONE", "Europe/Rome")
        self.max_daily_items = int(os.getenv("SHORTS_DAILY_MAX_ITEMS", "6"))
        self.enabled = os.getenv("SHORTS_DAILY_AUTONOMY_ENABLED", "true").lower() == "true"
        self.breaking_enabled = os.getenv("SHORTS_BREAKING_EXTRAS_ENABLED", "true").lower() == "true"
        self.breaking_min_score = int(os.getenv("SHORTS_BREAKING_MIN_SCORE", "70"))
        self.breaking_max_age_hours = int(os.getenv("SHORTS_BREAKING_MAX_AGE_HOURS", "8"))
        self.breaking_cooldown_minutes = int(os.getenv("SHORTS_BREAKING_COOLDOWN_MINUTES", "180"))
        dawn_hhmm = os.getenv("SHORTS_DAILY_DAWN_TIME", "05:30")
        self.dawn_hour, self.dawn_minute = self._parse_hhmm(dawn_hhmm, default_hour=5, default_minute=30)

    @staticmethod
    def _parse_hhmm(value: str, default_hour: int, default_minute: int) -> tuple[int, int]:
        try:
            hour_s, minute_s = str(value or "").strip().split(":", 1)
            hour = int(hour_s)
            minute = int(minute_s)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
        except Exception:
            pass
        return default_hour, default_minute

    def now_local(self) -> datetime:
        return datetime.now(ZoneInfo(self.timezone))

    def get_today_dawn(self, now_local: datetime | None = None) -> datetime:
        local_now = now_local or self.now_local()
        tz = ZoneInfo(self.timezone)
        day = local_now.astimezone(tz).date()
        return datetime.combine(day, time(hour=self.dawn_hour, minute=self.dawn_minute), tzinfo=tz)

    def should_run_automatic_reconcile(self, now_local: datetime | None = None) -> bool:
        if not self.enabled:
            return False
        local_now = now_local or self.now_local()
        return local_now >= self.get_today_dawn(local_now)

    def reconcile_today_plan(self, force: bool = False) -> dict:
        if not self.enabled:
            return {"status": "disabled"}
        now_local = self.now_local()
        target_date = now_local.date().isoformat()
        current = get_daily_plan(target_date)
        if current and not force:
            summary = summarize_plan_status(target_date)
            # If the day already has work in progress, do not overwrite.
            if sum(summary.values()) > 0:
                return {
                    "status": "existing",
                    "target_date": target_date,
                    "summary": summary,
                }

        from newsica.agents.content_strategist import ContentStrategistAgent
        strategist = ContentStrategistAgent()
        all_news = strategist._collect_news(force_fetch=False) or []
        items = self._build_items(all_news, now_local.date(), now_local=now_local)
        plan_payload = {
            "target_date": target_date,
            "timezone": self.timezone,
            "generated_at": now_local.isoformat(),
            "constraints": {
                "always": list(ALWAYS_MODES),
                "conditional": list(CONDITIONAL_MODES),
            },
            "hot_windows": DEFAULT_HOT_WINDOWS,
            "item_count": len(items),
        }
        saved = save_daily_plan(
            target_date=target_date,
            status="planned",
            reason="auto_daily_planning",
            plan_payload=plan_payload,
            items=items,
        )
        return {
            "status": "planned" if saved else "error",
            "target_date": target_date,
            "item_count": len(items),
        }

    def ensure_breaking_extra_if_needed(self, now_local: datetime | None = None) -> dict:
        if not self.enabled or not self.breaking_enabled:
            return {"status": "disabled"}
        local_now = now_local or self.now_local()
        if not self.should_run_automatic_reconcile(now_local=local_now):
            return {"status": "pre_dawn"}

        target_date = local_now.date().isoformat()
        day_plan = get_daily_plan(target_date)
        if not day_plan:
            return {"status": "no_plan", "target_date": target_date}

        items = list_plan_items(target_date)
        if self._has_active_breaking_item(items, local_now):
            return {"status": "existing_breaking", "target_date": target_date}

        all_news = self._load_recent_news()
        candidate, score = self._select_breaking_candidate(all_news, local_now)
        if not candidate:
            return {"status": "no_candidate", "target_date": target_date}
        if score < self.breaking_min_score:
            return {"status": "below_threshold", "target_date": target_date, "score": score}

        candidate_title = (candidate.get("title") or "").strip().lower()
        for row in items:
            if (row.get("source_title") or "").strip().lower() == candidate_title:
                return {"status": "duplicate_title", "target_date": target_date}

        extra_item = {
            "mode": "breaking",
            "rule_type": "extra",
            "reason": f"breaking_extra:score={score}",
            "priority": 140,
            "source_title": candidate.get("title", ""),
            "source_summary": candidate.get("summary") or candidate.get("description", ""),
            "source_score": score,
            "scheduled_for": self._compute_breaking_schedule(local_now),
            "status": "planned",
        }
        saved = add_plan_item(target_date, extra_item)
        return {
            "status": "planned" if saved else "error",
            "target_date": target_date,
            "score": score,
            "title": candidate.get("title", ""),
        }

    def _build_items(self, all_news: list[dict], target_day: date, now_local: datetime | None = None) -> list[dict]:
        selected_titles = set()
        candidates_by_mode = {
            "news": self._rank_candidates("news", all_news),
            "funfact": self._rank_candidates("funfact", all_news),
            "tech": self._rank_candidates("tech", all_news),
            "meteo": self._rank_candidates("meteo", all_news),
            "sport": self._rank_candidates("sport", all_news),
            "wellness": self._rank_candidates("wellness", all_news),
            "motori": self._rank_candidates("motori", all_news),
        }

        planned_modes = []
        # Always-on pillars
        for mode in ALWAYS_MODES:
            planned_modes.append((mode, "always"))

        # Conditional themes
        for mode in CONDITIONAL_MODES:
            if self._is_mode_relevant(mode, candidates_by_mode.get(mode, [])):
                planned_modes.append((mode, "conditional"))

        # Keep output bounded and diverse.
        planned_modes = planned_modes[: self.max_daily_items]
        items = []
        for index, (mode, rule_type) in enumerate(planned_modes):
            picked = self._pick_candidate(candidates_by_mode.get(mode, []), selected_titles)
            if picked:
                selected_titles.add((picked.get("title") or "").strip().lower())
            source_title = (picked or {}).get("title", "")
            source_summary = (picked or {}).get("summary") or (picked or {}).get("description", "")
            source_score = int((picked or {}).get("_shorts_score", 0))
            scheduled_for = self._compute_platform_schedule(target_day, index, now_local=now_local)
            items.append(
                {
                    "mode": mode,
                    "rule_type": rule_type,
                    "reason": self._build_reason(mode, rule_type, source_score),
                    "priority": max(1, 100 - (index * 10)),
                    "source_title": source_title,
                    "source_summary": source_summary,
                    "source_score": source_score,
                    "scheduled_for": scheduled_for,
                    "status": "planned",
                }
            )
        return items

    def _build_reason(self, mode: str, rule_type: str, score: int) -> str:
        if rule_type == "always":
            return f"vincolo_obbligatorio:{mode}"
        return f"vincolo_condizionale:{mode}:score={score}"

    def _load_recent_news(self) -> list[dict]:
        from newsica.agents.content_strategist import ContentStrategistAgent
        strategist = ContentStrategistAgent()
        return strategist._collect_news(force_fetch=True) or []

    def _has_active_breaking_item(self, items: list[dict], now_local: datetime) -> bool:
        active_statuses = {"planned", "generating", "scheduled", "posted"}
        for item in items:
            mode = str(item.get("mode", "")).strip().lower()
            status = str(item.get("status", "")).strip().lower()
            if mode != "breaking" or status not in active_statuses:
                continue
            created_at = self._parse_local_datetime(item.get("created_at"))
            if not created_at:
                return True
            age_minutes = (now_local - created_at).total_seconds() / 60.0
            if age_minutes <= self.breaking_cooldown_minutes:
                return True
        return False

    def _parse_local_datetime(self, value) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text)
            tz = ZoneInfo(self.timezone)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone(tz)
        except Exception:
            return None

    def _parse_news_datetime(self, raw_value) -> datetime | None:
        text = str(raw_value or "").strip()
        if not text:
            return None
        tz = ZoneInfo(self.timezone)
        try:
            if text.endswith("Z"):
                text = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone(tz)
        except Exception:
            pass
        try:
            dt = parsedate_to_datetime(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone(tz)
        except Exception:
            return None

    def _select_breaking_candidate(self, all_news: list[dict], now_local: datetime) -> tuple[dict | None, int]:
        preferred_sources = {"ansa_ultimora", "agi_cronaca", "agi_estero", "agi_politica", "ansa_cronaca", "ansa_mondo"}
        fallback = []
        ranked = []
        for item in all_news or []:
            source = (item.get("source") or "").strip().lower()
            title = item.get("title") or ""
            summary = item.get("summary") or item.get("description") or ""
            if not title:
                continue
            if source not in preferred_sources:
                fallback.append(item)
                continue
            published_dt = self._parse_news_datetime(item.get("published") or item.get("publishedAt") or item.get("published_at"))
            if published_dt:
                age_hours = (now_local - published_dt).total_seconds() / 3600.0
                if age_hours > self.breaking_max_age_hours:
                    continue
            score, _, _ = assess_news_gravity(title, summary, category="breaking")
            ranked.append((score, item))

        if not ranked:
            for item in fallback[:5]:
                title = item.get("title") or ""
                summary = item.get("summary") or item.get("description") or ""
                if not title:
                    continue
                score, _, _ = assess_news_gravity(title, summary, category="breaking")
                ranked.append((score, item))

        if not ranked:
            return None, 0
        ranked.sort(key=lambda row: int(row[0]), reverse=True)
        score, item = ranked[0]
        return item, int(score)

    def _compute_breaking_schedule(self, now_local: datetime) -> dict:
        schedule = {}
        tz = ZoneInfo(self.timezone)
        offsets = {
            "youtube": 15,
            "instagram": 20,
            "tiktok": 25,
        }
        for platform, minutes in offsets.items():
            local_dt = now_local.astimezone(tz) + timedelta(minutes=minutes)
            schedule[platform] = {
                "local": local_dt.isoformat(),
                "utc": local_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        return schedule

    def _compute_platform_schedule(self, target_day: date, slot_index: int, now_local: datetime | None = None) -> dict:
        schedule = {}
        tz = ZoneInfo(self.timezone)
        for platform, times in DEFAULT_HOT_WINDOWS.items():
            if not times:
                continue
            if now_local is None:
                hhmm = times[min(slot_index, len(times) - 1)]
                hour, minute = [int(x) for x in hhmm.split(":")]
                local_dt = datetime.combine(target_day, time(hour=hour, minute=minute), tzinfo=tz)
            else:
                start_dt = now_local if now_local.tzinfo else now_local.replace(tzinfo=tz)
                start_dt = start_dt.astimezone(tz) + timedelta(minutes=1)
                candidates = []
                for day_offset in range(0, 7):
                    candidate_day = target_day + timedelta(days=day_offset)
                    for hhmm in times:
                        hour, minute = [int(x) for x in hhmm.split(":")]
                        candidate = datetime.combine(candidate_day, time(hour=hour, minute=minute), tzinfo=tz)
                        if candidate >= start_dt:
                            candidates.append(candidate)
                if not candidates:
                    candidate_day = target_day + timedelta(days=1)
                    hour, minute = [int(x) for x in times[0].split(":")]
                    local_dt = datetime.combine(candidate_day, time(hour=hour, minute=minute), tzinfo=tz)
                else:
                    local_dt = candidates[min(slot_index, len(candidates) - 1)]
            schedule[platform] = {
                "local": local_dt.isoformat(),
                "utc": local_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        return schedule

    def _is_mode_relevant(self, mode: str, ranked_candidates: list[dict]) -> bool:
        if not ranked_candidates:
            return False
        top_score = int(ranked_candidates[0].get("_shorts_score", 0))
        threshold = MODE_THRESHOLDS.get(mode, 50)
        return top_score >= threshold

    def _pick_candidate(self, ranked_candidates: list[dict], selected_titles: set[str]) -> dict | None:
        for item in ranked_candidates:
            title_key = (item.get("title") or "").strip().lower()
            if not title_key or title_key in selected_titles:
                continue
            return item
        return ranked_candidates[0] if ranked_candidates else None

    def _rank_candidates(self, mode: str, all_news: list[dict]) -> list[dict]:
        pool = self._filter_mode_pool(mode, all_news)
        ranked = []
        for item in pool:
            title = item.get("title", "")
            summary = item.get("summary") or item.get("description", "")
            score = calculate_heuristic_score(title, summary, category=mode)
            row = dict(item)
            row["_shorts_score"] = score
            ranked.append(row)
        ranked.sort(key=lambda x: int(x.get("_shorts_score", 0)), reverse=True)
        return ranked

    def _filter_mode_pool(self, mode: str, all_news: list[dict]) -> list[dict]:
        if mode == "news":
            return [
                item
                for item in all_news
                if item.get("source") not in {"ansa_sport", "agi_sport", "meteo", "ansa_motori"}
            ]
        if mode == "funfact":
            allowed = {
                "ansa_lifestyle",
                "ansa_cultura",
                "agi_cultura",
                "ansa_tecnologia",
                "agi_innovazione",
                "ansa_salute_benessere",
            }
            return [item for item in all_news if item.get("source") in allowed]
        allowed = MODE_SOURCE_MAP.get(mode, set())
        return [item for item in all_news if item.get("source") in allowed]
