from utils.atomic_write import atomic_write
"""
EchoHound User Memory Manager — fixed bugs 1, 2, 3
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

MEMORY_DIR = Path(__file__).parent / "users"
COMMUNITY_MEMORY_DIR = Path(__file__).parent
USER_META_FILE = Path(__file__).parent / "user_meta.json"

MAX_USER_CHARS = 6000
MAX_COMMUNITY_CHARS = 4000
MEMORY_EXPIRY_DAYS = 30

MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def _community_path(chat_id: int = 0) -> Path:
    return COMMUNITY_MEMORY_DIR / f"community_{chat_id}.md"

def _get_user_memory_path(user_id: int, chat_id: int = 0) -> Path:
    community_dir = MEMORY_DIR / str(chat_id)
    community_dir.mkdir(parents=True, exist_ok=True)
    return community_dir / f"{user_id}.md"

def _load_user_meta() -> Dict[str, Any]:
    if USER_META_FILE.exists():
        return json.loads(USER_META_FILE.read_text())
    return {}

def _save_user_meta(meta: Dict[str, Any]):
    atomic_write(str(USER_META_FILE), json.dumps(meta, indent=2))

def get_user_memory(user_id: int, chat_id: int = 0) -> str:
    path = _get_user_memory_path(user_id, chat_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")

def get_community_memory(chat_id: int = 0) -> str:
    p = _community_path(chat_id)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")

def write_user_memory(user_id: int, entry: str, user_name: Optional[str] = None, chat_id: int = 0):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"\n## {timestamp}\n{entry.strip()}\n"
    current = get_user_memory(user_id, chat_id)
    updated = current + new_entry
    if len(updated) > MAX_USER_CHARS:
        updated = _trim_oldest(updated, MAX_USER_CHARS)
    atomic_write(str(_get_user_memory_path(user_id, chat_id)), updated)
    meta = _load_user_meta()
    user_key = str(user_id)
    if user_key not in meta:
        meta[user_key] = {"first_seen": timestamp, "message_count": 0, "last_seen": timestamp, "user_name": user_name or "Unknown"}
    meta[user_key]["message_count"] = meta[user_key].get("message_count", 0) + 1
    meta[user_key]["last_seen"] = timestamp
    if user_name:
        meta[user_key]["user_name"] = user_name
    _save_user_meta(meta)

def write_community_memory(entry: str, chat_id: int = 0):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"\n## {timestamp}\n{entry.strip()}\n"
    current = get_community_memory(chat_id)
    updated = current + new_entry
    if len(updated) > MAX_COMMUNITY_CHARS:
        updated = _trim_oldest(updated, MAX_COMMUNITY_CHARS)
    atomic_write(str(_community_path(chat_id)), updated)

def clear_user_memory(user_id: int, chat_id: int = 0):
    path = _get_user_memory_path(user_id, chat_id)
    if path.exists():
        atomic_write(str(path), "# EchoHound Memory\n\n## Cleared\nMemory wiped by user.\n")

def clear_community_memory(chat_id: int = 0):
    atomic_write(str(_community_path(chat_id)), "# EchoHound Community Memory\n\n## Cleared\nCommunity memory wiped.\n")

def get_user_summary(user_id: int) -> str:
    meta = _load_user_meta()
    user_key = str(user_id)
    if user_key not in meta:
        return ""
    user = meta[user_key]
    return f"User: {user.get('user_name','Unknown')} | Messages: {user.get('message_count',0)} | First seen: {user.get('first_seen','Unknown')}"

def get_active_users(days: int = 7) -> list:
    meta = _load_user_meta()
    cutoff = datetime.now() - timedelta(days=days)
    active = []
    for user_id, data in meta.items():
        try:
            last_dt = datetime.strptime(data.get("last_seen", ""), "%Y-%m-%d %H:%M")
            if last_dt >= cutoff:
                active.append(int(user_id))
        except:
            pass
    return active

def _trim_oldest(content: str, max_chars: int) -> str:
    lines = content.splitlines(keepends=True)
    section_starts = [i for i, l in enumerate(lines) if l.startswith("## ")]
    if len(section_starts) <= 2:
        return content[-max_chars:]
    drop_start = section_starts[1]
    drop_end = section_starts[2] if len(section_starts) > 2 else len(lines)
    lines = lines[:drop_start] + lines[drop_end:]
    result = "".join(lines)
    if len(result) > max_chars:
        return _trim_oldest(result, max_chars)
    return result

def memory_for_prompt(user_id: int, chat_id: int = 0) -> str:
    parts = []
    user_mem = get_user_memory(user_id, chat_id)
    if user_mem.strip() and not user_mem.strip().endswith("Memory wiped by user."):
        parts.append(f"## What you remember about this user:\n{user_mem}")
    comm_mem = get_community_memory(chat_id)
    if comm_mem.strip():
        parts.append(f"## Community knowledge:\n{comm_mem}")
    if parts:
        return "\n\n---\n" + "\n\n---\n".join(parts) + "\n---\n"
    return ""

def cleanup_expired_memories():
    cutoff = datetime.now() - timedelta(days=MEMORY_EXPIRY_DAYS)
    for mem_file in MEMORY_DIR.rglob("*.md"):
        content = mem_file.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        filtered = []
        current_section = []
        current_date = None
        for line in lines:
            if line.startswith("## "):
                if current_date and current_date >= cutoff:
                    filtered.extend(current_section)
                current_section = [line]
                try:
                    current_date = datetime.strptime(line[3:].strip(), "%Y-%m-%d %H:%M")
                except:
                    current_date = None
            else:
                current_section.append(line)
        if current_date and current_date >= cutoff:
            filtered.extend(current_section)
        atomic_write(str(mem_file), "".join(filtered))
