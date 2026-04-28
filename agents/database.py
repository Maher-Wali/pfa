from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from passlib.context import CryptContext


Mode = Literal["content_creation", "virtual_therapy"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ConversationDB:
    def __init__(self, db_path: str = "data/conversations.sqlite3"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    title TEXT,
                    safety_status TEXT DEFAULT 'NOT_CRITICAL',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id)
                        REFERENCES conversations(id)
                        ON DELETE CASCADE
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_user
                ON conversations(user_id)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id)
                """
            )

    def create_user(self, username: str, password: str) -> str:
        user_id = str(uuid.uuid4())
        now = self._now()
        password_hash = pwd_context.hash(password)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (id, username, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, username, password_hash, now),
            )

        return user_id

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

        return dict(row) if row else None

    def verify_user(self, username: str, password: str) -> dict[str, Any] | None:
        user = self.get_user_by_username(username)

        if not user:
            return None

        if not pwd_context.verify(password, user["password_hash"]):
            return None

        return user

    def create_conversation(
        self,
        user_id: str,
        mode: Mode,
        title: str | None = None,
    ) -> str:
        conversation_id = str(uuid.uuid4())
        now = self._now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (
                    id, user_id, mode, title, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    user_id,
                    mode,
                    title or self._default_title(mode),
                    now,
                    now,
                ),
            )

        return conversation_id

    def add_message(
        self,
        conversation_id: str,
        role: Literal["user", "assistant", "system"],
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        message_id = str(uuid.uuid4())
        now = self._now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, role, content, metadata, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )

            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, conversation_id),
            )

        return message_id

    def update_safety_status(self, conversation_id: str, safety_status: str) -> None:
        now = self._now()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET safety_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (safety_status, now, conversation_id),
            )

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()

        return dict(row) if row else None

    def list_conversations(
        self,
        user_id: str,
        mode: Mode | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT *
            FROM conversations
            WHERE user_id = ?
        """
        params: list[Any] = [user_id]

        if mode:
            query += " AND mode = ?"
            params.append(mode)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [dict(row) for row in rows]

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            ).fetchall()

        messages = []

        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"] or "{}")
            messages.append(item)

        return messages

    def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()

        messages = []

        for row in reversed(rows):
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"] or "{}")
            messages.append(item)

        return messages

    def count_assistant_messages(self, conversation_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM messages
                WHERE conversation_id = ?
                AND role = 'assistant'
                """,
                (conversation_id,),
            ).fetchone()

        return int(row["count"])

    def _default_title(self, mode: Mode) -> str:
        if mode == "content_creation":
            return "Content Creation Conversation"

        return "Virtual Therapy Conversation"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()