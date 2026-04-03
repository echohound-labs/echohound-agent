"""
EchoHound — Conv Archive (FTS5)
================================
Indexes every inbound and outbound message into a local SQLite FTS5 database.
Zero cost. Zero external dependencies. 26ms search latency.

Architecture inspired by OpenClaw conv-archive FTS5 system.
"""

import sqlite3
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("echohound.conv_archive")

DB_PATH = Path(__file__).parent.parent / "data" / "conversations.db"

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction TEXT NOT NULL,
            sender_name TEXT,
            content TEXT NOT NULL,
            chat_id INTEGER,
            channel TEXT DEFAULT 'telegram',
            timestamp_ms INTEGER NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content,
            sender_name,
            direction,
            channel,
            content='messages',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS messages_ai
        AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content, sender_name, direction, channel)
            VALUES (new.id, new.content, new.sender_name, new.direction, new.channel);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_ad
        AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content, sender_name, direction, channel)
            VALUES ('delete', old.id, old.content, old.sender_name, old.direction, old.channel);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_au_old
        AFTER UPDATE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content, sender_name, direction, channel)
            VALUES ('delete', old.id, old.content, old.sender_name, old.direction, old.channel);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_au_new
        AFTER UPDATE ON messages BEGIN
            INSERT INTO messages_fts(rowid, content, sender_name, direction, channel)
            VALUES (new.id, new.content, new.sender_name, new.direction, new.channel);
        END;
    """)
    conn.commit()

class ConvArchive:
    def __init__(self):
        self._conn = _get_conn()
        _init_db(self._conn)
        logger.info(f"[ConvArchive] Ready — {DB_PATH}")

    def write_message(
        self,
        direction: str,
        sender_name: str,
        content: str,
        chat_id: int = 0,
        channel: str = "telegram",
    ):
        if not content or not content.strip():
            return
        ts = int(time.time() * 1000)
        try:
            self._conn.execute(
                "INSERT INTO messages (direction, sender_name, content, chat_id, channel, timestamp_ms) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (direction, sender_name, content.strip(), chat_id, channel, ts),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning(f"[ConvArchive] Write failed: {e}")

    def count(self) -> int:
        try:
            row = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()
            return row[0] if row else 0
        except Exception:
            return 0
