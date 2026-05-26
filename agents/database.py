from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Literal

import psycopg2
import psycopg2.extras


Mode = Literal["content_creation", "virtual_therapy"]


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


class ConversationDB:
    def __init__(self):
        self._init_db()

    def _init_db(self) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        title TEXT,
                        safety_status TEXT DEFAULT 'NOT_CRITICAL',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                cur.execute("""
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
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conversations_user
                    ON conversations(user_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id)
                """)

    def create_conversation(
        self,
        user_id: str,
        mode: Mode,
        title: str | None = None,
    ) -> str:
        conversation_id = str(uuid.uuid4())
        now = self._now()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations (id, user_id, mode, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (conversation_id, user_id, mode, title or self._default_title(mode), now, now),
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
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO messages (id, conversation_id, role, content, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
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
                cur.execute(
                    "UPDATE conversations SET updated_at = %s WHERE id = %s",
                    (now, conversation_id),
                )
        return message_id

    def update_safety_status(self, conversation_id: str, safety_status: str) -> None:
        now = self._now()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversations SET safety_status = %s, updated_at = %s WHERE id = %s",
                    (safety_status, now, conversation_id),
                )

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM conversations WHERE id = %s", (conversation_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def list_conversations(
        self,
        user_id: str,
        mode: Mode | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM conversations WHERE user_id = %s"
        params: list[Any] = [user_id]
        if mode:
            query += " AND mode = %s"
            params.append(mode)
        query += " ORDER BY updated_at DESC LIMIT %s"
        params.append(limit)
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM messages WHERE conversation_id = %s ORDER BY created_at ASC",
                    (conversation_id,),
                )
                rows = cur.fetchall()
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
        with _connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM messages WHERE conversation_id = %s
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    (conversation_id, limit),
                )
                rows = cur.fetchall()
        messages = []
        for row in reversed(rows):
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"] or "{}")
            messages.append(item)
        return messages

    def count_assistant_messages(self, conversation_id: str) -> int:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM messages WHERE conversation_id = %s AND role = 'assistant'",
                    (conversation_id,),
                )
                return cur.fetchone()[0]

    def delete_conversation(self, conversation_id: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))

    def _default_title(self, mode: Mode) -> str:
        if mode == "content_creation":
            return "Content Creation Conversation"
        return "Virtual Therapy Conversation"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
