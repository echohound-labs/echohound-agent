"""
Memory Manager — KAIROS-style persistence
==========================================
EchoHound remembers things across conversations.
Inspired by the KAIROS + 'dream' consolidation engine found in the Claude Code leak.

How it works:
- Every conversation turn can write to memory.md
- Memory is injected into the system prompt on each new conversation
- When memory exceeds MAX_CHARS, oldest entries are trimmed first
- A 'dream' pass can summarize and compress old memories periodically
"""

import os
import re
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(__file__).parent / "memory.md"
MAX_CHARS = 8000


def read_memory() -> str:
    """Return current memory contents."""
    if not MEMORY_FILE.exists():
        return ""
    return MEMORY_FILE.read_text(encoding="utf-8")


def write_memory(entry: str) -> None:
    """
    Append a new memory entry with timestamp.
    Trims oldest entries if file exceeds MAX_CHARS.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"\n## {timestamp}\n{entry.strip()}\n"

    current = read_memory()
    updated = current + new_entry

    # Trim oldest entries if over limit
    if len(updated) > MAX_CHARS:
        updated = _trim_oldest(updated)

    MEMORY_FILE.write_text(updated, encoding="utf-8")


def clear_memory() -> None:
    """Wipe memory — use carefully."""
    MEMORY_FILE.write_text(
        "# EchoHound Memory\n\n## Cleared\nMemory wiped by user.\n",
        encoding="utf-8",
    )


def _trim_oldest(content: str) -> str:
    """
    Remove oldest ## sections until under MAX_CHARS.
    Preserves the header comment block and Bootstrap entry.
    """
    lines = content.splitlines(keepends=True)

    # Find section boundaries (lines starting with ## )
    section_starts = [i for i, l in enumerate(lines) if l.startswith("## ")]

    if len(section_starts) <= 2:
        # Only 1-2 sections — can't trim further, just truncate raw
        return content[-MAX_CHARS:]

    # Drop the second-oldest section (keep Bootstrap at index 0)
    drop_start = section_starts[1]
    drop_end = section_starts[2] if len(section_starts) > 2 else len(lines)
    lines = lines[:drop_start] + lines[drop_end:]
    result = "".join(lines)

    if len(result) > MAX_CHARS:
        return _trim_oldest(result)  # recurse until under limit
    return result


def memory_summary_prompt(memory: str) -> str:
    """
    Format memory for injection into the system prompt.
    Returns empty string if no meaningful memory.
    """
    if not memory.strip() or memory.strip() == "# EchoHound Memory":
        return ""
    return f"\n\n---\n## What you remember:\n{memory}\n---\n"
