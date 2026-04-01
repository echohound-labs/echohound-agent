from utils.atomic_write import atomic_write
"""
EchoHound User Memory Manager
=============================
Per-user memory tracking with isolated conversations.
Each user gets their own memory file: memory/users/{user_id}.md

Features:
- Per-user persistent memory (KAIROS-style)
- Community memory for shared group knowledge
- Memory expiry (auto-trim old entries)
- User metadata tracking (first seen, message count, etc.)
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

MEMORY_DIR = Path(__file__).parent / "users"
COMMUNITY_MEMORY_DIR = Path(__file__).parent

def _community_path(chat_id: int = 0) -> Path:
    return COMMUNITY_MEMORY_DIR / f"community_{chat_id}.md"
USER_META_FILE = Path(__file__).parent / "user_meta.json"

MAX_USER_CHARS = 6000  # Per-user memory limit
MAX_COMMUNITY_CHARS = 4000  # Shared memory limit
MEMORY_EXPIRY_DAYS = 30

# Ensure directories exist
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _get_user_memory_path(user_id: int, chat_id: int = 0) -> Path:
    """Get the memory file path for a specific user."""
    community_dir = MEMORY_DIR / str(chat_id)
    community_dir.mkdir(parents=True, exist_ok=True)
    return community_dir / f"{user_id}.md"


def _load_user_meta() -> Dict[str, Any]:
    """Load user metadata tracking."""
    if USER_META_FILE.exists():
        return json.loads(USER_META_FILE.read_text())
    return {}


def _save_user_meta(meta: Dict[str, Any]):
    """Save user metadata tracking."""
    USER_META_FILE.write_text(json.dumps(meta, indent=2))


def get_user_memory(user_id: int, chat_id: int = 0) -> str:
    """Read memory for a specific user."""
    path = _get_user_memory_path(user_id, chat_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def get_community_memory(chat_id: int = 0) -> str:
    """Read shared community memory for a specific chat."""
    p = _community_path(chat_id)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def write_user_memory(user_id: int, entry: str, user_name: Optional[str] = None, chat_id: int = 0):
    """
    Append a memory entry for a specific user with timestamp.
    Trims oldest entries if file exceeds MAX_USER_CHARS.
    Also updates user metadata.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"\n## {timestamp}\n{entry.strip()}\n"
    
    current = get_user_memory(user_id, chat_id)
    updated = current + new_entry
    
    # Trim oldest entries if over limit
    if len(updated) > MAX_USER_CHARS:
        updated = _trim_oldest(updated, MAX_USER_CHARS)
    
    _get_user_memory_path(user_id, chat_id).write_text(updated, encoding="utf-8")
    
    # Update user metadata
    meta = _load_user_meta()
    user_key = str(user_id)
    
    if user_key not in meta:
        meta[user_key] = {
            "first_seen": timestamp,
            "message_count": 0,
            "last_seen": timestamp,
            "user_name": user_name or "Unknown"
        }
    
    meta[user_key]["message_count"] = meta[user_key].get("message_count", 0) + 1
    meta[user_key]["last_seen"] = timestamp
    if user_name:
        meta[user_key]["user_name"] = user_name
    
    _save_user_meta(meta)


def write_community_memory(entry: str, chat_id: int = 0):
    """
    Append a memory entry to shared community memory.
    Use for facts relevant to the whole group.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"\n## {timestamp}\n{entry.strip()}\n"
    
    current = get_community_memory()
    updated = current + new_entry
    
    if len(updated) > MAX_COMMUNITY_CHARS:
        updated = _trim_oldest(updated, MAX_COMMUNITY_CHARS)
    
    atomic_write(str(COMMUNITY_MEMORY), updated)


def clear_user_memory(user_id: int):
    """Wipe memory for a specific user."""
    path = _get_user_memory_path(user_id)
    if path.exists():
        path.write_text(
            "# EchoHound Memory\n\n## Cleared\nMemory wiped by user.\n",
            encoding="utf-8",
        )


def clear_community_memory():
    """Wipe shared community memory."""
    COMMUNITY_MEMORY.write_text(
        "# EchoHound Community Memory\n\n## Cleared\nCommunity memory wiped.\n",
        encoding="utf-8",
    )


def get_user_summary(user_id: int) -> str:
    """Get a brief summary of the user for context injection."""
    meta = _load_user_meta()
    user_key = str(user_id)
    
    if user_key not in meta:
        return ""
    
    user = meta[user_key]
    count = user.get("message_count", 0)
    first = user.get("first_seen", "Unknown")
    name = user.get("user_name", "Unknown")
    
    return f"User: {name} | Messages: {count} | First seen: {first}"


def get_active_users(days: int = 7) -> list:
    """Get list of recently active user IDs."""
    meta = _load_user_meta()
    cutoff = datetime.now() - timedelta(days=days)
    active = []
    
    for user_id, data in meta.items():
        last_seen = data.get("last_seen", "")
        try:
            last_dt = datetime.strptime(last_seen, "%Y-%m-%d %H:%M")
            if last_dt >= cutoff:
                active.append(int(user_id))
        except:
            pass
    
    return active


def _trim_oldest(content: str, max_chars: int) -> str:
    """
    Remove oldest ## sections until under max_chars.
    Keeps the header.
    """
    lines = content.splitlines(keepends=True)
    section_starts = [i for i, l in enumerate(lines) if l.startswith("## ")]
    
    if len(section_starts) <= 2:
        return content[-max_chars:]
    
    # Drop second-oldest section (keep header)
    drop_start = section_starts[1]
    drop_end = section_starts[2] if len(section_starts) > 2 else len(lines)
    lines = lines[:drop_start] + lines[drop_end:]
    result = "".join(lines)
    
    if len(result) > max_chars:
        return _trim_oldest(result, max_chars)
    return result


def memory_for_prompt(user_id: int) -> str:
    """
    Format user + community memory for injection into system prompt.
    """
    parts = []
    
    # User memory
    user_mem = get_user_memory(user_id)
    if user_mem.strip() and not user_mem.strip().endswith("Memory wiped by user."):
        parts.append(f"## What you remember about this user:\n{user_mem}")
    
    # Community memory
    comm_mem = get_community_memory()
    if comm_mem.strip():
        parts.append(f"## Community knowledge:\n{comm_mem}")
    
    if parts:
        return "\n\n---\n" + "\n\n---\n".join(parts) + "\n---\n"
    return ""


def cleanup_expired_memories():
    """
    Remove entries older than MEMORY_EXPIRY_DAYS from all memory files.
    Call this periodically (e.g., via cron or on startup).
    """
    cutoff = datetime.now() - timedelta(days=MEMORY_EXPIRY_DAYS)
    
    for mem_file in MEMORY_DIR.glob("*.md"):
        content = mem_file.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        
        # Parse and filter by date
        filtered = []
        current_section = []
        current_date = None
        
        for line in lines:
            if line.startswith("## "):
                # Process previous section
                if current_date and current_date >= cutoff:
                    filtered.extend(current_section)
                
                # Start new section
                current_section = [line]
                date_str = line[3:].strip()
                try:
                    current_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                except:
                    current_date = None
            else:
                current_section.append(line)
        
        # Don't forget last section
        if current_date and current_date >= cutoff:
            filtered.extend(current_section)
        
        atomic_write(str(mem_file), "".join(filtered))
