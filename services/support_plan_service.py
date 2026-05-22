from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from constants.support_messages import SUPPORT_MESSAGES
from services.whatsapp_service import WhatsAppSendResult, send_whatsapp_message
from session.store import _DB_PATH, SessionStore
from session.users import UserStore


SUPPORT_PLAN_ACCOUNT_NOTE = (
    "\n\nOptional WhatsApp check-ins were not started because this account does "
    "not have a valid phone number and explicit WhatsApp consent yet. You can "
    "update this in Profile settings."
)

SUPPORT_PLAN_STARTED_NOTE = (
    "\n\nI also started the optional WhatsApp check-ins you opted into. Day 1 "
    "has been sent, and you can reply STOP or disable the plan in settings."
)

SUPPORT_PLAN_ALREADY_ACTIVE_NOTE = (
    "\n\nYour optional WhatsApp check-ins are already active. You can reply STOP "
    "or disable the plan in settings."
)

SUPPORT_PLAN_SETUP_NOTE = (
    "\n\nOptional WhatsApp check-ins could not be started because messaging is "
    "not configured yet. Please check the app setup."
)

SUPPORT_PLAN_SCHEDULER_NOTE = (
    "\n\nDay 1 was sent, but follow-up scheduling is not running in this process. "
    "Install APScheduler or run a persistent worker for the remaining check-ins."
)


@dataclass
class SupportPlanActivationResult:
    activated: bool
    already_active: bool = False
    blocked_reason: str | None = None
    user_note: str | None = None
    day1_sent: bool = False
    provider_result: WhatsAppSendResult | None = None


@dataclass
class SupportPlanSendResult:
    sent: bool
    day: int | None = None
    completed: bool = False
    error: str | None = None
    provider_result: WhatsAppSendResult | None = None


class SupportPlanService:
    def __init__(
        self,
        db_path: Path | None = None,
        sender: Callable[[str, str], WhatsAppSendResult] | None = None,
    ):
        self._session_store = SessionStore(db_path)
        self._user_store = UserStore(db_path)
        self._db_path = db_path or _DB_PATH
        self._sender = sender or send_whatsapp_message

    def _open(self):
        return self._session_store._open()

    def activate_support_plan(
        self,
        user_id: str | None,
        mode: str | None = None,
    ) -> SupportPlanActivationResult:
        if not user_id:
            return SupportPlanActivationResult(
                activated=False,
                blocked_reason="missing_user",
                user_note=SUPPORT_PLAN_ACCOUNT_NOTE,
            )

        user = self._user_store.get_by_id(user_id)
        if not user or not user.phone_number or not user.whatsapp_opt_in:
            return SupportPlanActivationResult(
                activated=False,
                blocked_reason="missing_phone_or_opt_in",
                user_note=SUPPORT_PLAN_ACCOUNT_NOTE,
            )

        active = self.get_active_plan(user_id)
        if active:
            return SupportPlanActivationResult(
                activated=False,
                already_active=True,
                user_note=SUPPORT_PLAN_ALREADY_ACTIVE_NOTE,
            )

        selected_mode = mode or os.environ.get("SUPPORT_PLAN_MODE", "demo")
        total_days = _env_int("SUPPORT_PLAN_TOTAL_DAYS", 30)
        total_days = max(1, min(total_days, len(SUPPORT_MESSAGES)))

        provider_result = self._sender(user.phone_number, SUPPORT_MESSAGES[0])
        if not provider_result.success:
            return SupportPlanActivationResult(
                activated=False,
                blocked_reason="send_failed",
                user_note=SUPPORT_PLAN_SETUP_NOTE,
                provider_result=provider_result,
            )

        now = time.time()
        plan_id = str(uuid.uuid4())
        provider_ids = self._append_provider_message_id(
            existing=[],
            day=1,
            sent_at=now,
            result=provider_result,
        )
        active_flag = 0 if total_days == 1 else 1
        completed_at = now if total_days == 1 else None

        with self._open() as conn:
            conn.execute(
                """INSERT INTO support_plans
                   (plan_id, user_id, active, current_day, total_days, mode,
                    started_at, last_sent_at, completed_at, provider_message_ids,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    plan_id,
                    user_id,
                    active_flag,
                    1,
                    total_days,
                    selected_mode,
                    now,
                    now,
                    completed_at,
                    json.dumps(provider_ids),
                    now,
                    now,
                ),
            )
            conn.commit()

        return SupportPlanActivationResult(
            activated=True,
            user_note=SUPPORT_PLAN_STARTED_NOTE,
            day1_sent=True,
            provider_result=provider_result,
        )

    def send_next_day(self, user_id: str) -> SupportPlanSendResult:
        plan = self.get_active_plan(user_id)
        if not plan:
            return SupportPlanSendResult(sent=False, completed=True)

        next_day = int(plan["current_day"]) + 1
        total_days = int(plan["total_days"])
        if next_day > total_days:
            self._complete_plan(plan["plan_id"])
            return SupportPlanSendResult(sent=False, completed=True)

        user = self._user_store.get_by_id(user_id)
        if not user or not user.phone_number or not user.whatsapp_opt_in:
            self.disable_active_plan(user_id)
            return SupportPlanSendResult(
                sent=False,
                day=next_day,
                completed=True,
                error="missing_phone_or_opt_in",
            )

        provider_result = self._sender(user.phone_number, SUPPORT_MESSAGES[next_day - 1])
        if not provider_result.success:
            return SupportPlanSendResult(
                sent=False,
                day=next_day,
                error=provider_result.error,
                provider_result=provider_result,
            )

        now = time.time()
        existing_ids = json.loads(plan["provider_message_ids"] or "[]")
        provider_ids = self._append_provider_message_id(
            existing=existing_ids,
            day=next_day,
            sent_at=now,
            result=provider_result,
        )
        active = 0 if next_day >= total_days else 1
        completed_at = now if next_day >= total_days else None

        with self._open() as conn:
            conn.execute(
                """UPDATE support_plans
                   SET current_day = ?, active = ?, last_sent_at = ?,
                       completed_at = ?, provider_message_ids = ?, updated_at = ?
                   WHERE plan_id = ?""",
                (
                    next_day,
                    active,
                    now,
                    completed_at,
                    json.dumps(provider_ids),
                    now,
                    plan["plan_id"],
                ),
            )
            conn.commit()

        return SupportPlanSendResult(
            sent=True,
            day=next_day,
            completed=next_day >= total_days,
            provider_result=provider_result,
        )

    def get_active_plan(self, user_id: str):
        with self._open() as conn:
            return conn.execute(
                "SELECT * FROM support_plans "
                "WHERE user_id = ? AND active = 1 "
                "ORDER BY started_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()

    def list_active_plans(self):
        with self._open() as conn:
            return conn.execute(
                "SELECT * FROM support_plans WHERE active = 1"
            ).fetchall()

    def disable_active_plan(self, user_id: str) -> None:
        with self._open() as conn:
            conn.execute(
                "UPDATE support_plans SET active = 0, completed_at = ?, "
                "updated_at = ? WHERE user_id = ? AND active = 1",
                (time.time(), time.time(), user_id),
            )
            conn.commit()

    def _complete_plan(self, plan_id: str) -> None:
        now = time.time()
        with self._open() as conn:
            conn.execute(
                "UPDATE support_plans SET active = 0, completed_at = ?, "
                "updated_at = ? WHERE plan_id = ?",
                (now, now, plan_id),
            )
            conn.commit()

    @staticmethod
    def _append_provider_message_id(
        existing: list,
        day: int,
        sent_at: float,
        result: WhatsAppSendResult,
    ) -> list:
        out = list(existing)
        out.append(
            {
                "day": day,
                "provider": result.provider,
                "message_id": result.message_id,
                "sent_at": sent_at,
            }
        )
        return out


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default
