"""SQLite-backed preference store for the Mini App API.

Replaces the bot's in-memory `context.chat_data` so prefs survive restarts. Reuses the
transport-agnostic `ChatPreferences` model and its dict (de)serialization (`load_prefs`/
`save_prefs`) — the dict is persisted as a JSON blob keyed by Telegram user id.
"""

from __future__ import annotations

import json
import sqlite3
import time

from writer_ai_assistant.preferences import ChatPreferences, load_prefs, save_prefs


class PreferencesStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_preferences (
                    user_id    INTEGER PRIMARY KEY,
                    prefs_json TEXT    NOT NULL,
                    updated_at REAL    NOT NULL
                )
                """
            )

    def load(self, user_id: int) -> ChatPreferences:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT prefs_json FROM chat_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()

        if row is None:
            return ChatPreferences()

        try:
            data = json.loads(row[0])
        except (ValueError, TypeError):
            return ChatPreferences()
        return load_prefs(data)

    def save(self, user_id: int, prefs: ChatPreferences) -> None:
        data: dict = {}
        save_prefs(data, prefs)
        payload = json.dumps(data)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_preferences (user_id, prefs_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    prefs_json = excluded.prefs_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, payload, time.time()),
            )
