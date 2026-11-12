"""
database/db.py
--------------
Thin, thread-safe wrapper around SQLite. Stores chats, their messages and the
long-term memory entries. The schema is embedded here (and mirrored in
database/schema.sql) so the frozen .exe needs no extra data files.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from settings.config import app_data_dir

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS chats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role        TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT    NOT NULL,
    model       TEXT,
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages (chat_id, id);
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content     TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL
);
"""


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


class Database:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else app_data_dir() / "randans_gpt.db"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------ helpers
    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -------------------------------------------------------------- chats
    def create_chat(self, title: str) -> int:
        now = _now()
        return self._execute(
            "INSERT INTO chats (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, now, now),
        ).lastrowid

    def list_chats(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM chats ORDER BY updated_at DESC, id DESC")

    def get_chat(self, chat_id: int) -> Optional[dict[str, Any]]:
        rows = self._query("SELECT * FROM chats WHERE id = ?", (chat_id,))
        return rows[0] if rows else None

    def rename_chat(self, chat_id: int, title: str) -> None:
        self._execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))

    def delete_chat(self, chat_id: int) -> None:
        self._execute("DELETE FROM chats WHERE id = ?", (chat_id,))

    # ----------------------------------------------------------- messages
    def add_message(self, chat_id: int, role: str, content: str,
                    model: Optional[str] = None) -> int:
        now = _now()
        cur = self._execute(
            "INSERT INTO messages (chat_id, role, content, model, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, role, content, model, now),
        )
        self._execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
        return cur.lastrowid

    def get_messages(self, chat_id: int) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,))

    def get_recent_messages(self, chat_id: int, limit: int) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        )
        return list(reversed(rows))

    # ----------------------------------------------------------- memories
    def add_memory(self, content: str) -> bool:
        """Store a memory. Returns False if it already existed."""
        cur = self._execute(
            "INSERT OR IGNORE INTO memories (content, created_at) VALUES (?, ?)",
            (content, _now()),
        )
        return cur.rowcount > 0

    def list_memories(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM memories ORDER BY id")

    def delete_memory(self, memory_id: int) -> None:
        self._execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def clear_memories(self) -> int:
        return self._execute("DELETE FROM memories").rowcount

    # -------------------------------------------------------------- stats
    def stats(self) -> dict:
        """Numbers for the dashboard."""
        one = lambda sql: self._query(sql)[0]["c"]  # noqa: E731
        by_model = self._query(
            "SELECT model, COUNT(*) AS c FROM messages WHERE role = 'assistant' "
            "AND model IS NOT NULL AND model != 'memory' GROUP BY model ORDER BY c DESC")
        daily = {r["d"]: r["c"] for r in self._query(
            "SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS c FROM messages "
            "WHERE role = 'user' AND substr(created_at, 1, 10) >= date('now', 'localtime', '-6 days') "
            "GROUP BY d")}
        return {
            "chats": one("SELECT COUNT(*) AS c FROM chats"),
            "messages": one("SELECT COUNT(*) AS c FROM messages"),
            "questions": one("SELECT COUNT(*) AS c FROM messages WHERE role = 'user'"),
            "memories": one("SELECT COUNT(*) AS c FROM memories"),
            "by_model": by_model,
            "daily": daily,
        }
