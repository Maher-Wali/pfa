import json
import time
import uuid
from dataclasses import dataclass
from typing import List

import bcrypt as _bcrypt
import psycopg2.extras

from session.store import _connect


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
    def __init__(self):
        self._init_db()

    def _init_db(self) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id             TEXT PRIMARY KEY,
                        email               TEXT NOT NULL UNIQUE,
                        password_hash       TEXT NOT NULL,
                        age                 INTEGER,
                        goals               TEXT NOT NULL DEFAULT '[]',
                        job                 TEXT,
                        relationship_status TEXT,
                        created_at          REAL NOT NULL,
                        updated_at          REAL NOT NULL
                    )
                """)

    # ------------------------------------------------------------------
    # Account creation & lookup
    # ------------------------------------------------------------------

    def create_user(self, email: str, password: str, goals: List[str] | None = None) -> User:
        if self.get_by_email(email) is not None:
            raise ValueError(f"Email already registered: {email!r}")

        user_id = str(uuid.uuid4())
        password_hash = _hash_password(password)
        now = time.time()

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO users (user_id, email, password_hash, goals, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (user_id, email, password_hash, json.dumps(goals or []), now, now),
                )

        return User(user_id=user_id, email=email, goals=goals or [], created_at=now, updated_at=now)

    def authenticate(self, email: str, password: str) -> User | None:
        row = self._row_by_email(email)
        if row is None:
            return None
        if not _verify_password(password, row["password_hash"]):
            return None
        return self._row_to_user(row)

    def get_by_id(self, user_id: str) -> User | None:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
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
            fields.append("age = %s")
            values.append(age)
        if goals is not None:
            fields.append("goals = %s")
            values.append(json.dumps(goals))
        if job is not None:
            fields.append("job = %s")
            values.append(job)
        if relationship_status is not None:
            fields.append("relationship_status = %s")
            values.append(relationship_status)
        if not fields:
            return
        fields.append("updated_at = %s")
        values.append(time.time())
        values.append(user_id)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE users SET {', '.join(fields)} WHERE user_id = %s",
                    values,
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_by_email(self, email: str):
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                return cur.fetchone()

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
