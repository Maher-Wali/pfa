"""
Test suite runner — calls agents directly (no web server needed).

Usage:
    python tests/run_suites.py                  # run all suites
    python tests/run_suites.py --suite classifier
    python tests/run_suites.py --suite therapy_single
    python tests/run_suites.py --suite therapy_multi
    python tests/run_suites.py --suite content_single
    python tests/run_suites.py --suite content_multi

Results are written to tests/results/<timestamp>/
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.config import get_settings
from agents.content_agent import ContentCreationAgent
from agents.database import ConversationDB
from agents.therapy_agent import VirtualTherapyAgent
from safety_classifier.classifier import SafetyClassifier
from session.users import UserStore

FIXTURES = Path(__file__).parent / "fixtures"
RESULTS = Path(__file__).parent / "results"

TEST_USER_EMAIL = "test-suite@pfa.internal"
TEST_USER_PASSWORD = "test-suite-pw"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_test_user(user_store: UserStore) -> str:
    user = user_store.get_by_email(TEST_USER_EMAIL)
    if user:
        return user.user_id
    user = user_store.create_user(email=TEST_USER_EMAIL, password=TEST_USER_PASSWORD)
    return user.user_id


def _last_assistant_meta(db: ConversationDB, conversation_id: str) -> dict:
    messages = db.get_messages(conversation_id)
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            return msg.get("metadata") or {}
    return {}


def _load_yaml(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save(run_dir: Path, filename: str, data: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / filename
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  -> saved {out.relative_to(Path(__file__).parent)}")


def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _progress(msg: str) -> None:
    print(f"  {msg}", flush=True)


# ---------------------------------------------------------------------------
# Classifier suite
# ---------------------------------------------------------------------------

def run_classifier(run_dir: Path, settings) -> dict:
    print("\n[classifier]")
    data = _load_yaml("classifier.yaml")
    clf = SafetyClassifier(settings.classifier_model_name)

    results = []
    passed = failed = 0

    for case in data["cases"]:
        try:
            got = clf.is_crisis(case["input"])
            ok = got == case["expected"]
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1
            _progress(f"[{status}] {case['id']}  got={'crisis' if got else 'safe'}  expected={'crisis' if case['expected'] else 'safe'}  | {case['input'][:60]}")
            results.append({
                "id": case["id"],
                "input": case["input"],
                "expected": case["expected"],
                "got": got,
                "pass": ok,
            })
        except Exception as exc:
            _progress(f"[ERROR] {case['id']}: {exc}")
            results.append({"id": case["id"], "input": case["input"], "error": str(exc)})
            failed += 1

    total = passed + failed
    print(f"  => {passed}/{total} passed")

    output = {
        "suite": "classifier",
        "run_at": _ts(),
        "cases": results,
        "summary": {"total": total, "passed": passed, "failed": failed},
    }
    _save(run_dir, "classifier.json", output)
    return output


# ---------------------------------------------------------------------------
# Single-turn suite (shared for both agents)
# ---------------------------------------------------------------------------

def run_single_turn(run_dir: Path, fixture_name: str, agent, db: ConversationDB, user_id: str) -> dict:
    data = _load_yaml(fixture_name)
    agent_name = data["agent"]
    suite_key = fixture_name.replace(".yaml", "")
    print(f"\n[{suite_key}]")

    results = []

    for case in data["cases"]:
        _progress(f"running {case['id']} — {case['label']} ...")
        t0 = time.time()
        try:
            response = agent.respond(
                user_id=user_id,
                user_input=case["input"],
            )
            meta = _last_assistant_meta(db, response["conversation_id"])
            elapsed = round(time.time() - t0, 1)
            _progress(f"  done in {elapsed}s")
            results.append({
                "id": case["id"],
                "label": case["label"],
                "input": case["input"],
                "retrieval_mode": meta.get("retrieval_mode"),
                "rag_docs": meta.get("rag_docs", []),
                "draft": meta.get("draft"),
                "critique": meta.get("critique"),
                "final_answer": response["answer"],
                "safe_mode": response.get("safe_mode", False),
                "elapsed_s": elapsed,
            })
        except Exception as exc:
            elapsed = round(time.time() - t0, 1)
            _progress(f"  ERROR: {exc}")
            traceback.print_exc()
            results.append({
                "id": case["id"],
                "label": case["label"],
                "input": case["input"],
                "error": str(exc),
                "elapsed_s": elapsed,
            })

    output = {
        "suite": suite_key,
        "agent": agent_name,
        "run_at": _ts(),
        "cases": results,
    }
    _save(run_dir, f"{suite_key}.json", output)
    return output


# ---------------------------------------------------------------------------
# Multi-turn suite (shared for both agents)
# ---------------------------------------------------------------------------

def run_multi_turn(run_dir: Path, fixture_name: str, agent, db: ConversationDB, user_id: str) -> dict:
    data = _load_yaml(fixture_name)
    agent_name = data["agent"]
    suite_key = fixture_name.replace(".yaml", "")
    print(f"\n[{suite_key}]")

    conversations = []

    for conv in data["conversations"]:
        _progress(f"conversation {conv['id']} — {conv['label']}")
        conversation_id = agent.create_conversation(user_id=user_id)
        turns = []

        for i, message in enumerate(conv["turns"], 1):
            _progress(f"  turn {i}/{len(conv['turns'])} ...")
            t0 = time.time()
            try:
                response = agent.respond(
                    user_id=user_id,
                    user_input=message,
                    conversation_id=conversation_id,
                )
                meta = _last_assistant_meta(db, conversation_id)
                elapsed = round(time.time() - t0, 1)
                _progress(f"    done in {elapsed}s")
                turns.append({
                    "turn": i,
                    "input": message,
                    "retrieval_mode": meta.get("retrieval_mode"),
                    "rag_docs": meta.get("rag_docs", []),
                    "draft": meta.get("draft"),
                    "critique": meta.get("critique"),
                    "final_answer": response["answer"],
                    "safe_mode": response.get("safe_mode", False),
                    "elapsed_s": elapsed,
                })
            except Exception as exc:
                elapsed = round(time.time() - t0, 1)
                _progress(f"    ERROR: {exc}")
                traceback.print_exc()
                turns.append({
                    "turn": i,
                    "input": message,
                    "error": str(exc),
                    "elapsed_s": elapsed,
                })

        conversations.append({
            "id": conv["id"],
            "label": conv["label"],
            "conversation_id": conversation_id,
            "turns": turns,
        })

    output = {
        "suite": suite_key,
        "agent": agent_name,
        "run_at": _ts(),
        "conversations": conversations,
    }
    _save(run_dir, f"{suite_key}.json", output)
    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run agent test suites")
    parser.add_argument(
        "--suite",
        choices=["classifier", "therapy_single", "therapy_multi", "content_single", "content_multi", "all"],
        default="all",
    )
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = RESULTS / run_id
    print(f"Run ID: {run_id}")
    print(f"Output: {run_dir}")

    settings = get_settings()
    db = ConversationDB(settings.sqlite_db_path)
    user_store = UserStore()
    user_id = _get_or_create_test_user(user_store)
    print(f"Test user: {TEST_USER_EMAIL} ({user_id})")

    run_all = args.suite == "all"

    if run_all or args.suite == "classifier":
        run_classifier(run_dir, settings)

    therapy_agent = None
    content_agent = None

    if run_all or args.suite in {"therapy_single", "therapy_multi"}:
        print("\nLoading therapy agent...")
        therapy_agent = VirtualTherapyAgent(settings=settings, db=db)

    if run_all or args.suite in {"content_single", "content_multi"}:
        print("\nLoading content agent...")
        content_agent = ContentCreationAgent(settings=settings, db=db)

    if run_all or args.suite == "therapy_single":
        run_single_turn(run_dir, "therapy_single_turn.yaml", therapy_agent, db, user_id)

    if run_all or args.suite == "therapy_multi":
        run_multi_turn(run_dir, "therapy_multi_turn.yaml", therapy_agent, db, user_id)

    if run_all or args.suite == "content_single":
        run_single_turn(run_dir, "content_single_turn.yaml", content_agent, db, user_id)

    if run_all or args.suite == "content_multi":
        run_multi_turn(run_dir, "content_multi_turn.yaml", content_agent, db, user_id)

    print(f"\nAll done. Results in tests/results/{run_id}/")


if __name__ == "__main__":
    main()
