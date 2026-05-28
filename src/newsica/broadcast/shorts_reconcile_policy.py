import time


class ShortsReconcilePolicy:
    def __init__(self, shorts_planner, *, breaking_probe_interval_seconds: int = 600):
        self.shorts_planner = shorts_planner
        self._last_shorts_plan_date = None
        self._last_shorts_pre_dawn_skip_date = None
        self._last_breaking_shorts_probe_at = 0.0
        self._breaking_shorts_probe_interval_seconds = int(breaking_probe_interval_seconds)

    def reconcile_daily_if_needed(self):
        now_local = self.shorts_planner.now_local()
        today = now_local.date().isoformat()
        if self._last_shorts_plan_date == today:
            return
        if not self.shorts_planner.should_run_automatic_reconcile(now_local=now_local):
            if self._last_shorts_pre_dawn_skip_date != today:
                dawn = self.shorts_planner.get_today_dawn(now_local=now_local)
                print(
                    f"🌅 [DirectorAgent] Pianificazione shorts rinviata: prima dell'alba "
                    f"({dawn.strftime('%H:%M')} {self.shorts_planner.timezone})."
                )
                self._last_shorts_pre_dawn_skip_date = today
            return
        try:
            result = self.shorts_planner.reconcile_today_plan(force=False)
            status = result.get("status")
            if status in {"planned", "existing", "disabled"}:
                self._last_shorts_plan_date = today
        except Exception as e:
            print(f"⚠️ [DirectorAgent] Errore pianificazione shorts giornaliera: {e}")

    def reconcile_breaking_if_needed(self):
        now_ts = time.time()
        if self._last_breaking_shorts_probe_at and (
            now_ts - self._last_breaking_shorts_probe_at < max(30, self._breaking_shorts_probe_interval_seconds)
        ):
            return
        self._last_breaking_shorts_probe_at = now_ts
        try:
            result = self.shorts_planner.ensure_breaking_extra_if_needed()
            if result.get("status") == "planned":
                title = result.get("title", "breaking news")
                score = result.get("score", 0)
                print(f"🚨 [DirectorAgent] Inserito short breaking straordinario (score={score}): {title}")
        except Exception as e:
            print(f"⚠️ [DirectorAgent] Errore controllo shorts breaking straordinari: {e}")
