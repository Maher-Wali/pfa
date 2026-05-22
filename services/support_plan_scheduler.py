from __future__ import annotations

import os
from datetime import datetime, timedelta

from services.support_plan_service import SupportPlanService

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ModuleNotFoundError:  # pragma: no cover - requirements install covers prod
    BackgroundScheduler = None


class SupportPlanScheduler:
    """
    In-process scheduler for demo/Streamlit use.

    This is intentionally thin so the same service can later be run from a
    persistent worker process for production reliability.
    """

    def __init__(self, service: SupportPlanService | None = None):
        self.service = service or SupportPlanService()
        self.available = BackgroundScheduler is not None
        self.scheduler = BackgroundScheduler() if self.available else None
        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()

    def schedule_existing_active_plans(self) -> bool:
        if not self.available:
            return False
        for plan in self.service.list_active_plans():
            self.schedule_user(plan["user_id"], plan["mode"])
        return True

    def schedule_user(self, user_id: str, mode: str | None = None) -> bool:
        if not self.available:
            return False

        selected_mode = mode or os.environ.get("SUPPORT_PLAN_MODE", "demo")
        job_id = self._job_id(user_id)
        if selected_mode == "production":
            hour = _env_int("SUPPORT_PLAN_MORNING_HOUR", 9)
            self.scheduler.add_job(
                self._send_and_maybe_stop,
                trigger="cron",
                hour=hour,
                minute=0,
                args=[user_id],
                id=job_id,
                replace_existing=True,
            )
        else:
            minutes = _env_int("SUPPORT_PLAN_INTERVAL_MINUTES", 5)
            self.scheduler.add_job(
                self._send_and_maybe_stop,
                trigger="interval",
                minutes=minutes,
                next_run_time=self.next_run_time_for_mode("demo"),
                args=[user_id],
                id=job_id,
                replace_existing=True,
            )
        return True

    def next_run_time_for_mode(
        self,
        mode: str,
        now: datetime | None = None,
    ) -> datetime:
        base = now or datetime.now()
        if mode == "production":
            hour = _env_int("SUPPORT_PLAN_MORNING_HOUR", 9)
            candidate = base.replace(hour=hour, minute=0, second=0, microsecond=0)
            return candidate if candidate > base else candidate + timedelta(days=1)

        minutes = _env_int("SUPPORT_PLAN_INTERVAL_MINUTES", 5)
        return base + timedelta(minutes=minutes)

    def run_due_for_tests(self, user_id: str):
        return self._send_and_maybe_stop(user_id)

    def _send_and_maybe_stop(self, user_id: str):
        result = self.service.send_next_day(user_id)
        if result.completed and self.available:
            job = self.scheduler.get_job(self._job_id(user_id))
            if job:
                job.remove()
        return result

    @staticmethod
    def _job_id(user_id: str) -> str:
        return f"support_plan_{user_id}"


_scheduler: SupportPlanScheduler | None = None


def get_support_plan_scheduler(
    service: SupportPlanService | None = None,
) -> SupportPlanScheduler:
    global _scheduler
    if _scheduler is None or service is not None:
        _scheduler = SupportPlanScheduler(service)
        _scheduler.schedule_existing_active_plans()
    return _scheduler


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default
