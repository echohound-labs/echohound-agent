"""
utils/exporter.py — Export user memory as JSON
Called by /xexport command in telegram_bot_v2.py
"""
import json
import time
from memory.session_memory import get_session_memory, get_typed_memories
from memory.user_manager import get_user_memory


def export_user_memory(user_id: int, username: str = "") -> dict:
    """Serialize all memory for a user into a JSON-exportable dict."""
    return {
        "exported_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "user_id": user_id,
        "username": username,
        "long_term_memory": get_user_memory(user_id),
        "session_notes": get_session_memory(user_id),
        "typed_memories": {
            "user":      get_typed_memories(user_id, "user"),
            "feedback":  get_typed_memories(user_id, "feedback"),
            "project":   get_typed_memories(user_id, "project"),
            "reference": get_typed_memories(user_id, "reference"),
        },
    }


def export_as_json(user_id: int, username: str = "") -> str:
    return json.dumps(export_user_memory(user_id, username), indent=2)
