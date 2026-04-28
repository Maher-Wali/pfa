import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List

import bcrypt as _bcrypt

from session.store import _DB_PATH, SessionStore


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


@dataclass
class User:
    user_id: str
    email: str
    age: int
    mood_baseline: int
    goals: List[str]
    country: str | None = None
    job: str | None = None
    relationship_status: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def profile_complete(self) -> bool:
        """True once both passively-extracted fields are filled."""
        return self.job is not None and self.relationship_status is not None


class UserStore:
    """User account operations backed by the shared SQLite database."""

    def __init__(self, db_path: Path | None = None):
        # Bootstrap is handled by SessionStore — instantiate it to ensure
        # the schema exists before we touch the users table.
        self._session_store = SessionStore(db_path)
        self._db_path = db_path or _DB_PATH

    def _open(self):
        return self._session_store._open()

    # ------------------------------------------------------------------
    # Account creation & lookup
    # ------------------------------------------------------------------

    def create_user(
        self,
        email: str,
        password: str,
        age: int,
        mood_baseline: int,
        goals: List[str],
        country: str | None = None,
    ) -> User:
        if self.get_by_email(email) is not None:
            raise ValueError(f"Email already registered: {email!r}")

        user_id = str(uuid.uuid4())
        password_hash = _hash_password(password)
        now = time.time()

        with self._open() as conn:
            conn.execute(
                """INSERT INTO users
                   (user_id, email, password_hash, age, country,
                    mood_baseline, goals, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, email, password_hash, age, country,
                    mood_baseline, json.dumps(goals), now, now,
                ),
            )
            conn.commit()

        return User(
            user_id=user_id,
            email=email,
            age=age,
            mood_baseline=mood_baseline,
            goals=goals,
            country=country,
            created_at=now,
            updated_at=now,
        )

    def authenticate(self, email: str, password: str) -> User | None:
        """Return the User if credentials are valid, else None."""
        row = self._row_by_email(email)
        if row is None:
            return None
        if not _verify_password(password, row["password_hash"]):
            return None
        return self._row_to_user(row)

    def get_by_id(self, user_id: str) -> User | None:
        with self._open() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        row = self._row_by_email(email)
        return self._row_to_user(row) if row else None

    # ------------------------------------------------------------------
    # Profile updates
    # ------------------------------------------------------------------

    def update_extracted_fields(
        self,
        user_id: str,
        job: str | None = None,
        relationship_status: str | None = None,
    ) -> None:
        """Update whichever extracted fields are provided (non-None only)."""
        fields, values = [], []
        if job is not None:
            fields.append("job = ?")
            values.append(job)
        if relationship_status is not None:
            fields.append("relationship_status = ?")
            values.append(relationship_status)
        if not fields:
            return
        fields.append("updated_at = ?")
        values.append(time.time())
        values.append(user_id)
        with self._open() as conn:
            conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?",
                values,
            )
            conn.commit()

    def update_country(self, user_id: str, country: str) -> None:
        with self._open() as conn:
            conn.execute(
                "UPDATE users SET country = ?, updated_at = ? WHERE user_id = ?",
                (country, time.time(), user_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_by_email(self, email: str):
        with self._open() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()

    @staticmethod
    def _row_to_user(row) -> User:
        return User(
            user_id=row["user_id"],
            email=row["email"],
            age=row["age"],
            mood_baseline=row["mood_baseline"],
            goals=json.loads(row["goals"]),
            country=row["country"],
            job=row["job"],
            relationship_status=row["relationship_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
