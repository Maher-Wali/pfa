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
    goals: List[str]
    age: int | None = None
    job: str | None = None
    relationship_status: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def profile_complete(self) -> bool:
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
        goals: List[str] | None = None,
    ) -> User:
        if self.get_by_email(email) is not None:
            raise ValueError(f"Email already registered: {email!r}")

        user_id = str(uuid.uuid4())
        password_hash = _hash_password(password)
        now = time.time()

        with self._open() as conn:
            conn.execute(
                """INSERT INTO users
                   (user_id, email, password_hash, goals, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, email, password_hash, json.dumps(goals or []), now, now),
            )
            conn.commit()

        return User(
            user_id=user_id,
            email=email,
            goals=goals or [],
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
        age: int | None = None,
        goals: List[str] | None = None,
        job: str | None = None,
        relationship_status: str | None = None,
    ) -> None:
        fields, values = [], []
        if age is not None:
            fields.append("age = ?")
            values.append(age)
        if goals is not None:
            fields.append("goals = ?")
            values.append(json.dumps(goals))
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
            goals=json.loads(row["goals"]),
            job=row["job"],
            relationship_status=row["relationship_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
