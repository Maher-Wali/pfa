from __future__ import annotations

import os
import py_compile
import sqlite3
import sys
import tempfile
import types
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _install_import_stubs() -> None:
    safety_mod = types.ModuleType("safety_classifier.classifier")

    class StubSafetyClassifier:
        def __init__(self, *args, **kwargs):
            pass

        def is_crisis(self, text: str) -> bool:
            return False

    safety_mod.SafetyClassifier = StubSafetyClassifier
    sys.modules.setdefault("safety_classifier.classifier", safety_mod)

    rag_mod = types.ModuleType("retrieval.rag_pipeline")

    class StubMentalHealthRAG:
        def generate_response(self, *args, **kwargs):
            return "stub"

    rag_mod.MentalHealthRAG = StubMentalHealthRAG
    sys.modules.setdefault("retrieval.rag_pipeline", rag_mod)

    openai_mod = types.ModuleType("openai")
    openai_mod.OpenAI = object
    sys.modules.setdefault("openai", openai_mod)


_install_import_stubs()

import chat_pipeline
from constants.support_messages import (
    FORBIDDEN_SUPPORT_MESSAGE_WORDS,
    SUPPORT_MESSAGES,
)
from services.support_plan_scheduler import SupportPlanScheduler
from services.support_plan_service import SupportPlanService
from services.whatsapp_service import WhatsAppSendResult
from session.store import SessionStore
from session.users import UserStore


class AlwaysCrisis:
    def is_crisis(self, text: str) -> bool:
        return True


class NeverCrisis:
    def is_crisis(self, text: str) -> bool:
        return False


class ExplodingRAG:
    def generate_response(self, *args, **kwargs) -> str:
        raise AssertionError("RAG should not run for crisis messages")


class SafeRAG:
    chat_history = []

    def generate_response(self, *args, **kwargs) -> str:
        return "non-crisis response"


class FakeScheduler:
    def __init__(self):
        self.scheduled: list[tuple[str, str]] = []

    def schedule_user(self, user_id: str, mode: str | None = None) -> bool:
        self.scheduled.append((user_id, mode or "demo"))
        return True


class RecordingSender:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def __call__(self, phone_number: str, body: str) -> WhatsAppSendResult:
        self.sent.append((phone_number, body))
        return WhatsAppSendResult(
            success=True,
            message_id=f"msg-{len(self.sent)}",
        )


def _active_plan_count(db_path: Path, user_id: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM support_plans WHERE user_id = ? AND active = 1",
            (user_id,),
        ).fetchone()
    return int(row[0])


def _patch_pipeline(
    store: SessionStore,
    user_store: UserStore,
    service: SupportPlanService,
    scheduler,
    classifier,
    rag,
) -> None:
    chat_pipeline._session_store = store
    chat_pipeline._user_store = user_store
    chat_pipeline._support_plan_service = service
    chat_pipeline._support_scheduler = scheduler
    chat_pipeline._classifier = classifier
    chat_pipeline._rag = rag


def assert_support_messages_are_safe() -> None:
    assert len(SUPPORT_MESSAGES) == 30
    for message in SUPPORT_MESSAGES:
        lowered = message.lower()
        assert not any(word in lowered for word in FORBIDDEN_SUPPORT_MESSAGE_WORDS)


def assert_crisis_counts_and_activation() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "sessions.db"
        store = SessionStore(db_path)
        user_store = UserStore(db_path)
        sender = RecordingSender()
        service = SupportPlanService(db_path, sender=sender)
        scheduler = FakeScheduler()
        user = user_store.create_user(
            email="demo@example.com",
            password="pw",
            age=25,
            mood_baseline=5,
            goals=["stay steady"],
            phone_number="+21612345678",
            whatsapp_opt_in=True,
        )
        session_id = store.create_session(user.user_id)

        _patch_pipeline(store, user_store, service, scheduler, AlwaysCrisis(), ExplodingRAG())

        chat_pipeline.run("crisis one", session_id)
        assert store.get_crisis_count(session_id) == 1
        assert len(sender.sent) == 0

        chat_pipeline.run("crisis two", session_id)
        assert store.get_crisis_count(session_id) == 2
        assert len(sender.sent) == 0

        result = chat_pipeline.run("crisis three", session_id)
        assert result.is_crisis is True
        assert store.get_crisis_count(session_id) == 3
        assert len(sender.sent) == 1
        assert _active_plan_count(db_path, user.user_id) == 1
        assert scheduler.scheduled == [(user.user_id, "demo")]

        chat_pipeline.run("crisis four", session_id)
        assert len(sender.sent) == 1
        assert _active_plan_count(db_path, user.user_id) == 1


def assert_non_crisis_resets_count() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "sessions.db"
        store = SessionStore(db_path)
        user_store = UserStore(db_path)
        sender = RecordingSender()
        service = SupportPlanService(db_path, sender=sender)
        user = user_store.create_user(
            email="reset@example.com",
            password="pw",
            age=25,
            mood_baseline=5,
            goals=["stay steady"],
            phone_number="+21612345678",
            whatsapp_opt_in=True,
        )
        session_id = store.create_session(user.user_id)
        store.increment_crisis_count(session_id)
        store.increment_crisis_count(session_id)

        _patch_pipeline(store, user_store, service, FakeScheduler(), NeverCrisis(), SafeRAG())
        result = chat_pipeline.run("What is anxiety?", session_id)
        assert result.is_crisis is False
        assert store.get_crisis_count(session_id) == 0


def assert_demo_schedule_sends_day_two() -> None:
    old_interval = os.environ.get("SUPPORT_PLAN_INTERVAL_MINUTES")
    os.environ["SUPPORT_PLAN_INTERVAL_MINUTES"] = "5"
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "sessions.db"
            user_store = UserStore(db_path)
            sender = RecordingSender()
            service = SupportPlanService(db_path, sender=sender)
            user = user_store.create_user(
                email="schedule@example.com",
                password="pw",
                age=25,
                mood_baseline=5,
                goals=["stay steady"],
                phone_number="+21612345678",
                whatsapp_opt_in=True,
            )
            activation = service.activate_support_plan(user.user_id, mode="demo")
            assert activation.activated is True
            assert len(sender.sent) == 1

            scheduler = SupportPlanScheduler(service)
            base = datetime(2026, 1, 1, 9, 0, 0)
            assert scheduler.next_run_time_for_mode("demo", base) == base + timedelta(minutes=5)

            send_result = scheduler.run_due_for_tests(user.user_id)
            assert send_result.sent is True
            assert send_result.day == 2
            assert len(sender.sent) == 2
    finally:
        if old_interval is None:
            os.environ.pop("SUPPORT_PLAN_INTERVAL_MINUTES", None)
        else:
            os.environ["SUPPORT_PLAN_INTERVAL_MINUTES"] = old_interval


def assert_missing_phone_or_opt_in_blocks_activation() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "sessions.db"
        store = SessionStore(db_path)
        user_store = UserStore(db_path)
        sender = RecordingSender()
        service = SupportPlanService(db_path, sender=sender)
        user = user_store.create_user(
            email="blocked@example.com",
            password="pw",
            age=25,
            mood_baseline=5,
            goals=["stay steady"],
            phone_number="+21612345678",
            whatsapp_opt_in=True,
        )
        user_store.update_whatsapp_settings(user.user_id, phone_number="", whatsapp_opt_in=False)
        session_id = store.create_session(user.user_id)

        _patch_pipeline(store, user_store, service, FakeScheduler(), AlwaysCrisis(), ExplodingRAG())
        chat_pipeline.run("crisis one", session_id)
        chat_pipeline.run("crisis two", session_id)
        result = chat_pipeline.run("crisis three", session_id)

        assert result.is_crisis is True
        assert "update this in Profile settings" in result.text
        assert len(sender.sent) == 0
        assert _active_plan_count(db_path, user.user_id) == 0


def assert_compile_smoke() -> None:
    for path in [
        ROOT / "app.py",
        ROOT / "chat_pipeline.py",
        ROOT / "session" / "store.py",
        ROOT / "session" / "users.py",
        ROOT / "services" / "whatsapp_service.py",
        ROOT / "services" / "support_plan_service.py",
        ROOT / "services" / "support_plan_scheduler.py",
        ROOT / "constants" / "support_messages.py",
    ]:
        py_compile.compile(str(path), doraise=True)


def main() -> None:
    checks = [
        assert_support_messages_are_safe,
        assert_crisis_counts_and_activation,
        assert_non_crisis_resets_count,
        assert_demo_schedule_sends_day_two,
        assert_missing_phone_or_opt_in_blocks_activation,
        assert_compile_smoke,
    ]
    for check in checks:
        check()
        print(f"OK: {check.__name__}")
    print("All support-plan validation checks passed.")


if __name__ == "__main__":
    main()
