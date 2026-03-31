"""
EchoHound Session Memory — Inspired by Claude Code Source (March 30, 2026 leak)
================================================================================
Implements the real SessionMemory pattern from Claude Code's source:

KEY INSIGHTS FROM THE LEAK:
1. Session memory uses a STRUCTURED TEMPLATE with fixed sections
2. It extracts memory in the BACKGROUND as a forked subagent (non-blocking)
3. It only fires when two thresholds are BOTH met: tokens AND tool calls
4. Memory has 4 TYPED categories: user, feedback, project, reference
5. The DREAM pass is a separate nightly consolidation job
6. Memory entries always include WHY + HOW TO APPLY, not just the fact
7. The template uses italic description lines that are NEVER overwritten

Template sections (from Claude Code's actual template):
  # Session Title
  # Current State
  # Task specification
  # Files and Functions
  # Workflow
  # Errors & Corrections
  # Codebase and System Documentation
  # Learnings
  # Key results
  # Worklog

Memory types (from memoryTypes.ts):
  user     — who they are, role, expertise, preferences
  feedback — corrections + confirmations (what to stop/keep doing)
  project  — ongoing work, goals, decisions (with absolute dates)
  reference — pointers to external systems
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

SESSION_MEMORY_DIR = Path(__file__).parent / "sessions"
USER_MEMORY_DIR = Path(__file__).parent / "users"
SESSION_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
USER_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# Thresholds (from Claude Code defaults)
MIN_MESSAGES_TO_INIT = 10       # Wait for real conversation depth
MIN_MESSAGES_BETWEEN_UPDATE = 5 # Don't update every message
TOOL_CALLS_BETWEEN_UPDATES = 3  # 3 tool uses = worth updating

# Max sizes (from Claude Code: 2000 tokens/section, 12000 total)
MAX_SECTION_CHARS = 8000
MAX_TOTAL_CHARS = 48000  # 12000 tokens * ~4 chars/token


SESSION_TEMPLATE = """# Session Title
_A short and distinctive 5-10 word descriptive title for the session._

# Current State
_What is actively being worked on? Pending tasks, immediate next steps._

# Task Specification
_What did the user ask to build? Any design decisions or context._

# Errors & Corrections
_Errors encountered and how they were fixed. What failed, what worked._

# Learnings
_What has worked well? What has not? What to avoid?_

# Key Results
_Any specific outputs, answers, or deliverables produced._

# Worklog
_Step by step, what was attempted and done? Terse, one line per step._
"""


# The 4 memory types from Claude Code's memoryTypes.ts
MEMORY_TYPES = {
    "user": {
        "desc": "User's role, expertise, preferences, knowledge",
        "when": "When you learn who they are or how they like to work",
        "format": "Fact. **Why it matters:** ... **Apply:** ...",
        "scope": "private",
    },
    "feedback": {
        "desc": "Corrections AND confirmations — what to stop/keep doing",
        "when": "User corrects you OR confirms an approach worked",
        "format": "Rule. **Why:** ... **How to apply:** ...",
        "scope": "private",
    },
    "project": {
        "desc": "Ongoing work, decisions, goals not in codebase",
        "when": "Who is doing what, why, by when (use absolute dates)",
        "format": "Fact. **Why:** ... **Apply:** ...",
        "scope": "community",
    },
    "reference": {
        "desc": "Pointers to external systems, docs, dashboards",
        "when": "User mentions an external resource and its purpose",
        "format": "Pointer + purpose.",
        "scope": "community",
    },
}


def get_session_memory_path(user_id: int) -> Path:
    return SESSION_MEMORY_DIR / f"{user_id}_session.md"


def get_user_typed_memory_path(user_id: int) -> Path:
    return USER_MEMORY_DIR / f"{user_id}.md"


def init_session_memory(user_id: int) -> str:
    """Create a session memory file from template if it doesn't exist."""
    path = get_session_memory_path(user_id)
    if not path.exists():
        path.write_text(SESSION_TEMPLATE, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def get_session_memory(user_id: int) -> str:
    """Read current session memory."""
    path = get_session_memory_path(user_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def clear_session_memory(user_id: int):
    """Reset session memory to fresh template."""
    path = get_session_memory_path(user_id)
    path.write_text(SESSION_TEMPLATE, encoding="utf-8")


def save_typed_memory(
    user_id: int,
    memory_type: str,
    content: str,
    user_name: Optional[str] = None,
) -> bool:
    """
    Save a typed memory entry for a user.
    
    Types: user, feedback, project, reference
    
    Content should follow the format:
      "Fact/rule. **Why:** reason. **Apply:** when to use."
    
    Returns True if saved, False if invalid type.
    """
    if memory_type not in MEMORY_TYPES:
        return False
    
    path = get_user_typed_memory_path(user_id)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    existing = path.read_text(encoding="utf-8") if path.exists() else f"# Memory: {user_name or user_id}\n\n"
    
    entry = f"\n### [{memory_type.upper()}] {timestamp}\n{content.strip()}\n"
    updated = existing + entry
    
    # Trim if over limit
    if len(updated) > MAX_TOTAL_CHARS:
        updated = _trim_oldest_entries(updated, MAX_TOTAL_CHARS)
    
    path.write_text(updated, encoding="utf-8")
    return True


def get_typed_memories(user_id: int, memory_type: Optional[str] = None) -> str:
    """Get all memories, optionally filtered by type."""
    path = get_user_typed_memory_path(user_id)
    if not path.exists():
        return ""
    
    content = path.read_text(encoding="utf-8")
    
    if not memory_type:
        return content
    
    # Filter to specific type
    lines = content.splitlines(keepends=True)
    in_section = False
    result = []
    
    for line in lines:
        if line.startswith(f"### [{memory_type.upper()}]"):
            in_section = True
        elif line.startswith("### [") and in_section:
            in_section = False
        
        if in_section:
            result.append(line)
    
    return "".join(result)


def build_memory_prompt_for_user(user_id: int) -> str:
    """
    Build the memory context block to inject into system prompt.
    Follows Claude Code's pattern: typed memories + current session state.
    """
    parts = []
    
    # Typed memories (user profile, feedback, etc.)
    typed_mem = get_typed_memories(user_id)
    if typed_mem.strip():
        parts.append(f"## What you know about this person:\n{typed_mem[:3000]}")
    
    # Current session state
    session_mem = get_session_memory(user_id)
    if session_mem.strip() and session_mem.strip() != SESSION_TEMPLATE.strip():
        parts.append(f"## Current session notes:\n{session_mem[:2000]}")
    
    if not parts:
        return ""
    
    return "\n\n---\n" + "\n\n---\n".join(parts) + "\n---\n"


def should_extract_memory(message_count: int, tool_call_count: int, last_extract_at: int) -> bool:
    """
    Check if we should run a memory extraction pass.
    Mirrors Claude Code's two-threshold gate:
      - Must have enough messages since last extraction
      - Must have enough tool calls too
    """
    if message_count < MIN_MESSAGES_TO_INIT:
        return False
    
    messages_since_last = message_count - last_extract_at
    if messages_since_last < MIN_MESSAGES_BETWEEN_UPDATE:
        return False
    
    if tool_call_count < TOOL_CALLS_BETWEEN_UPDATES:
        return False
    
    return True


def get_memory_update_prompt(user_id: int, session_memory_path: str) -> str:
    """
    Build the prompt to send to a background subagent for memory extraction.
    Directly inspired by Claude Code's session memory update prompt.
    """
    current = get_session_memory(user_id)
    
    return f"""BACKGROUND TASK — NOT part of the user conversation. Do not reference this in your response.

Update the session notes file with new information from the conversation above.

Current session notes:
<current_notes>
{current}
</current_notes>

RULES:
- NEVER modify section headers (lines starting with #)
- NEVER modify the italic _description_ lines — they are template instructions
- ONLY update the content BELOW each section's description
- Write DETAILED, info-dense content — file names, function names, exact errors
- Keep each section under {MAX_SECTION_CHARS} characters
- Focus on "Current State" — this is critical for continuity
- Convert any relative dates to absolute dates (e.g., "yesterday" → "2026-03-30")
- If nothing new to add to a section, leave it unchanged — no filler

Also identify any memories worth saving long-term. For each one, format as:
[SAVE_MEMORY type=<user|feedback|project|reference>]
The memory content here. Lead with the fact, then **Why:** and **Apply:**.
[/SAVE_MEMORY]

Save memories when:
- User corrects your approach (feedback memory)
- User confirms something worked (feedback memory)
- You learn about the user's expertise/role (user memory)
- You learn about ongoing project decisions (project memory)
- User mentions external system/doc locations (reference memory)

Do NOT save: code patterns, git history, debugging recipes, things in the codebase.
"""


def _trim_oldest_entries(content: str, max_chars: int) -> str:
    """Remove oldest ### entries until under limit."""
    if len(content) <= max_chars:
        return content
    
    lines = content.splitlines(keepends=True)
    section_starts = [i for i, l in enumerate(lines) if l.startswith("### [")]
    
    if len(section_starts) <= 1:
        return content[-max_chars:]
    
    # Drop oldest section
    drop_end = section_starts[1]
    lines = lines[:1] + lines[drop_end:]  # Keep header
    result = "".join(lines)
    
    return _trim_oldest_entries(result, max_chars) if len(result) > max_chars else result


def get_what_not_to_save() -> str:
    """What should NOT be saved (from Claude Code's memoryTypes.ts)."""
    return """
What NOT to save:
- Code patterns, architecture, file paths — derivable from the code
- Git history, recent changes — use git log/blame
- Debugging solutions — the fix is in the code
- Ephemeral task details, in-progress work, current conversation context
- Things already in config/docs files
"""
