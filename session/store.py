import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import List, Tuple

import psycopg2
import psycopg2.extras


SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


@contextmanager
def _connect():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class SessionStore:
    def __init__(self):
        self._init_db()

    def _init_db(self) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id               TEXT PRIMARY KEY,
                        user_id                  TEXT,
                        created_at               REAL NOT NULL,
                        last_active              REAL NOT NULL,
                        consecutive_crisis_count INTEGER NOT NULL DEFAULT 0,
                        last_crisis_detected_at  REAL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS turns (
                        id                SERIAL PRIMARY KEY,
                        session_id        TEXT NOT NULL,
                        user_message      TEXT NOT NULL,
                        assistant_message TEXT NOT NULL,
                        timestamp         REAL NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS support_plans (
                        plan_id              TEXT PRIMARY KEY,
                        user_id              TEXT NOT NULL,
                        active               INTEGER NOT NULL DEFAULT 1,
                        current_day          INTEGER NOT NULL DEFAULT 0,
                        total_days           INTEGER NOT NULL DEFAULT 30,
                        mode                 TEXT NOT NULL,
                        started_at           REAL NOT NULL,
                        last_sent_at         REAL,
                        completed_at         REAL,
                        provider_message_ids TEXT NOT NULL DEFAULT '[]',
                        created_at           REAL NOT NULL,
                        updated_at           REAL NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_support_plans_user ON support_plans(user_id)
                """)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, user_id: str | None = None) -> str:
        session_id = str(uuid.uuid4())
        now = time.time()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (session_id, user_id, created_at, last_active) VALUES (%s, %s, %s, %s)",
                    (session_id, user_id, now, now),
                )
        return session_id

    def session_exists(self, session_id: str) -> bool:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM sessions WHERE session_id = %s", (session_id,))
                return cur.fetchone() is not None

    def _touch(self, cur, session_id: str) -> None:
        cur.execute(
            "UPDATE sessions SET last_active = %s WHERE session_id = %s",
            (time.time(), session_id),
        )

    # ------------------------------------------------------------------
    # History access
    # ------------------------------------------------------------------

    def load_history(self, session_id: str, limit: int | None = None) -> List[Tuple[str, str]]:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if limit is not None:
                    cur.execute(
                        "SELECT user_message, assistant_message FROM turns "
                        "WHERE session_id = %s ORDER BY id DESC LIMIT %s",
                        (session_id, limit),
                    )
                    rows = cur.fetchall()
                    return [(r["user_message"], r["assistant_message"]) for r in reversed(rows)]
                cur.execute(
                    "SELECT user_message, assistant_message FROM turns "
                    "WHERE session_id = %s ORDER BY id ASC",
                    (session_id,),
                )
                rows = cur.fetchall()
        return [(r["user_message"], r["assistant_message"]) for r in rows]

    def count_turns(self, session_id: str) -> int:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM turns WHERE session_id = %s", (session_id,))
                return cur.fetchone()[0]

    def append_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        now = time.time()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO turns (session_id, user_message, assistant_message, timestamp) "
                    "VALUES (%s, %s, %s, %s)",
                    (session_id, user_message, assistant_message, now),
                )
                self._touch(cur, session_id)

    def get_user_id(self, session_id: str) -> str | None:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT user_id FROM sessions WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
        return row["user_id"] if row else None

    # ------------------------------------------------------------------
    # Crisis tracking
    # ------------------------------------------------------------------

    def increment_crisis_count(self, session_id: str) -> int:
        now = time.time()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions "
                    "SET consecutive_crisis_count = consecutive_crisis_count + 1, "
                    "last_crisis_detected_at = %s, last_active = %s "
                    "WHERE session_id = %s",
                    (now, now, session_id),
                )
                cur.execute(
                    "SELECT consecutive_crisis_count FROM sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
        return int(row[0]) if row else 0

    def reset_crisis_count(self, session_id: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions "
                    "SET consecutive_crisis_count = 0, last_crisis_detected_at = NULL, "
                    "last_active = %s WHERE session_id = %s",
                    (time.time(), session_id),
                )

    def get_crisis_count(self, session_id: str) -> int:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT consecutive_crisis_count FROM sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
        return int(row[0]) if row else 0

    def delete_session(self, session_id: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM turns WHERE session_id = %s", (session_id,))
                cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def purge_expired(self, ttl_seconds: int = SESSION_TTL_SECONDS) -> int:
        cutoff = time.time() - ttl_seconds
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id FROM sessions WHERE last_active < %s", (cutoff,)
                )
                ids = [r[0] for r in cur.fetchall()]
                if ids:
                    cur.execute(
                        "DELETE FROM turns WHERE session_id = ANY(%s)", (ids,)
                    )
                    cur.execute(
                        "DELETE FROM sessions WHERE session_id = ANY(%s)", (ids,)
                    )
        return len(ids)
