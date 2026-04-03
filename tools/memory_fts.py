"""
EchoHound — FTS5 Memory Search Tool
=====================================
Claude calls this when it needs to recall what was actually said.
BM25-ranked results from SQLite FTS5. ~26ms average.

Architecture inspired by OpenClaw conv-archive FTS5 system.
"""

import sqlite3
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("echohound.memory_fts")

DB_PATH = Path(__file__).parent.parent / "data" / "conversations.db"

FTS_TOOL_DEFINITION = {
    "name": "memory_fts_search",
    "description": (
        "Search the full conversation archive using fast BM25 keyword search. "
        "Use this to recall what someone ACTUALLY said, find specific facts from past conversations, "
        "or check conversation history. "
        "Query with keywords — not full sentences. "
        "Example: 'validator stake requirements' or 'Skywalker project deadline'. "
        "Returns ranked results with sender name, timestamp, and exact message content."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword search query. Use specific terms, not full sentences.",
            },
            "limit": {
                "type": "integer",
                "default": 8,
                "description": "Max results to return (default 8, max 20).",
            },
            "sender": {
                "type": "string",
                "description": "Optional: filter by sender name e.g. 'Skywalker'.",
            },
            "since_days": {
                "type": "integer",
                "description": "Optional: only return messages from the last N days.",
            },
        },
        "required": ["query"],
    },
}

def fts_search(
    query: str,
    limit: int = 8,
    sender: Optional[str] = None,
    since_days: Optional[int] = None,
) -> str:
    if not DB_PATH.exists():
        return "No conversation archive yet — messages will be indexed as the conversation continues."

    limit = min(int(limit), 20)

    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")

        if since_days:
            cutoff_ms = int((time.time() - since_days * 86400) * 1000)
            sql = f"""
                SELECT m.content, m.sender_name, m.direction, m.channel, m.timestamp_ms,
                       bm25(messages_fts) AS score
                FROM messages_fts
                JOIN messages m ON messages_fts.rowid = m.id
                WHERE messages_fts MATCH ?
                  AND m.timestamp_ms >= {cutoff_ms}
                  {"AND m.sender_name LIKE ?" if sender else ""}
                ORDER BY score
                LIMIT ?
            """
            p = [query] + ([f"%{sender}%"] if sender else []) + [limit]
        else:
            sql = f"""
                SELECT m.content, m.sender_name, m.direction, m.channel, m.timestamp_ms,
                       bm25(messages_fts) AS score
                FROM messages_fts
                JOIN messages m ON messages_fts.rowid = m.id
                WHERE messages_fts MATCH ?
                  {"AND m.sender_name LIKE ?" if sender else ""}
                ORDER BY score
                LIMIT ?
            """
            p = [query] + ([f"%{sender}%"] if sender else []) + [limit]

        rows = conn.execute(sql, p).fetchall()
        conn.close()

        if not rows:
            return f"No results found for: '{query}'"

        lines = [f"FTS5 search results for '{query}' ({len(rows)} found):\n"]
        for i, (content, sender_name, direction, channel, ts_ms, score) in enumerate(rows, 1):
            ts_str = _fmt_ts(ts_ms)
            arrow = "→" if direction == "assistant" else "←"
            preview = content[:300].replace("\n", " ")
            if len(content) > 300:
                preview += "..."
            lines.append(f"{i}. [{ts_str}] {arrow} {sender_name}: {preview}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"[FTS] Search error: {e}")
        return f"Search error: {e}"

def _fmt_ts(ts_ms: int) -> str:
    try:
        import datetime
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts_ms)
