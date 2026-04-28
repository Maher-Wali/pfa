import sqlite3
import time
import uuid
from pathlib import Path
from typing import List, Tuple

_DB_PATH = Path(__file__).parent.parent / "data" / "sessions.db"

# Sessions inactive longer than this are excluded from history loads.
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _bootstrap(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id             TEXT PRIMARY KEY,
            email               TEXT NOT NULL UNIQUE,
            password_hash       TEXT NOT NULL,
            age                 INTEGER NOT NULL,
            country             TEXT,
            mood_baseline       INTEGER NOT NULL,
            goals               TEXT NOT NULL DEFAULT '[]',
            job                 TEXT,
            relationship_status TEXT,
            created_at          REAL NOT NULL,
            updated_at          REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            user_id     TEXT,
            created_at  REAL NOT NULL,
            last_active REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS turns (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id         TEXT    NOT NULL,
            user_message       TEXT    NOT NULL,
            assistant_message  TEXT    NOT NULL,
            timestamp          REAL    NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    """)
    conn.commit()


class SessionStore:
    """SQLite-backed store for conversation sessions."""

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or _DB_PATH
        with self._open() as conn:
            _bootstrap(conn)

    def _open(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, user_id: str | None = None) -> str:
        session_id = str(uuid.uuid4())
        now = time.time()
        with self._open() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, user_id, created_at, last_active) VALUES (?, ?, ?, ?)",
                (session_id, user_id, now, now),
            )
            conn.commit()
        return session_id

    def session_exists(self, session_id: str) -> bool:
        with self._open() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return row is not None

    def _touch(self, conn: sqlite3.Connection, session_id: str) -> None:
        conn.execute(
            "UPDATE sessions SET last_active = ? WHERE session_id = ?",
            (time.time(), session_id),
        )

    # ------------------------------------------------------------------
    # History access
    # ------------------------------------------------------------------

    def load_history(self, session_id: str) -> List[Tuple[str, str]]:
        """Return all turns for *session_id* in chronological order."""
        with self._open() as conn:
            rows = conn.execute(
                "SELECT user_message, assistant_message FROM turns "
                "WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [(r["user_message"], r["assistant_message"]) for r in rows]

    def append_turn(
        self, session_id: str, user_message: str, assistant_message: str
    ) -> None:
        """Persist a single exchange and update the session's last_active timestamp."""
        now = time.time()
        with self._open() as conn:
            conn.execute(
                "INSERT INTO turns (session_id, user_message, assistant_message, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (session_id, user_message, assistant_message, now),
            )
            self._touch(conn, session_id)
            conn.commit()

    def get_user_id(self, session_id: str) -> str | None:
        with self._open() as conn:
            row = conn.execute(
                "SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return row["user_id"] if row else None

    def delete_session(self, session_id: str) -> None:
        with self._open() as conn:
            conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def purge_expired(self, ttl_seconds: int = SESSION_TTL_SECONDS) -> int:
        """Delete sessions (and their turns) inactive for longer than *ttl_seconds*.
        Returns the number of sessions removed."""
        cutoff = time.time() - ttl_seconds
        with self._open() as conn:
            expired = conn.execute(
                "SELECT session_id FROM sessions WHERE last_active < ?", (cutoff,)
            ).fetchall()
            ids = [r["session_id"] for r in expired]
            if ids:
                placeholders = ",".join("?" * len(ids))
                conn.execute(f"DELETE FROM turns WHERE session_id IN ({placeholders})", ids)
                conn.execute(f"DELETE FROM sessions WHERE session_id IN ({placeholders})", ids)
                conn.commit()
        return len(ids)
