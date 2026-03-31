"""
Session Memory System for EchoHound
Based on Claude Code's KAIROS architecture (March 2026 leak)

Implements:
- 9-section structured template
- 4-type memory taxonomy (user, feedback, project, reference)
- Two-threshold extraction gate
- Section size limits
"""

import os
import re
import json
from datetime import datetime
from typing import Optional, Literal
from dataclasses import dataclass, asdict

MemoryType = Literal["user", "feedback", "project", "reference"]

SECTION_TEMPLATE = """# Session: {title}

# Current State
{current_state}

# Task Specification
{task_spec}

# Files and Functions
{files_functions}

# Workflow
{workflow}

# Errors & Corrections
{errors}

# Learnings
{learnings}

# Key Results
{results}

# Worklog
{worklog}
"""

SECTION_LIMITS = {
    "current_state": 8000,
    "task_spec": 8000,
    "files_functions": 8000,
    "workflow": 8000,
    "errors": 8000,
    "learnings": 8000,
    "results": 8000,
    "worklog": 8000,
}

MAX_TOTAL_TOKENS = 48000


@dataclass
class MemoryEntry:
    """A single typed memory entry."""
    type: MemoryType
    content: str
    context: str
    timestamp: str
    source_session: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class SessionMemory:
    """
    Manages session-scoped memory using Claude Code's 9-section template.
    Extracts to long-term memory when both thresholds are hit.
    """

    def __init__(self, session_id: str, memory_dir: str = "./memory/sessions"):
        self.session_id = session_id
        self.memory_dir = memory_dir
        self.message_count = 0
        self.tool_call_count = 0

        # Thresholds for extraction (both must be hit)
        self.MESSAGE_THRESHOLD = 10
        self.TOOL_CALL_THRESHOLD = 3

        os.makedirs(memory_dir, exist_ok=True)
        self.session_path = os.path.join(memory_dir, f"{session_id}.md")

        # Initialize with empty template
        if not os.path.exists(self.session_path):
            self._init_template()

    def _init_template(self):
        """Create a new session file with empty template."""
        content = SECTION_TEMPLATE.format(
            title=self.session_id,
            current_state="No current task. Waiting for user input.",
            task_spec="No task specified yet.",
            files_functions="No files in context.",
            workflow="No workflow established.",
            errors="No errors yet.",
            learnings="No learnings yet.",
            results="No results yet.",
            worklog=f"Session started: {datetime.now().isoformat()}\n",
        )
        with open(self.session_path, "w") as f:
            f.write(content)

    def _read_section(self, section: str) -> str:
        """Read a specific section from the session file."""
        if not os.path.exists(self.session_path):
            return ""

        with open(self.session_path, "r") as f:
            content = f.read()

        # Match section content between header and next section
        pattern = rf"# {re.escape(section)}\n\n(.*?)(?=\n# |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _update_section(self, section: str, new_content: str):
        """Update a specific section, respecting size limits."""
        if not os.path.exists(self.session_path):
            self._init_template()

        with open(self.session_path, "r") as f:
            content = f.read()

        # Apply section size limit
        limit = SECTION_LIMITS.get(section.lower().replace(" ", "_"), 8000)
        if len(new_content) > limit:
            new_content = new_content[-limit:]  # Keep most recent

        # Replace section
        pattern = rf"(# {re.escape(section)}\n\n).*?(?=\n# |\Z)"
        replacement = rf"\g<1>{new_content}\n\n"
        new_content_full = re.sub(pattern, replacement, content, flags=re.DOTALL)

        with open(self.session_path, "w") as f:
            f.write(new_content_full)

    def update_current_state(self, state: str):
        """Update the Current State section (read first after gap)."""
        self._update_section("Current State", state)

    def update_task_spec(self, spec: str):
        """Update the Task Specification section."""
        self._update_section("Task Specification", spec)

    def add_file_reference(self, file_path: str, functions: list = None):
        """Add a file and its functions to the session context."""
        existing = self._read_section("Files and Functions")
        entry = f"- {file_path}"
        if functions:
            entry += f" (functions: {', '.join(functions)})"
        new_content = existing + "\n" + entry if existing else entry
        self._update_section("Files and Functions", new_content)

    def log_error(self, error: str, correction: str):
        """Log an error and its correction."""
        existing = self._read_section("Errors & Corrections")
        entry = f"[{datetime.now().isoformat()}] Error: {error}\nCorrection: {correction}\n"
        new_content = existing + "\n" + entry if existing else entry
        self._update_section("Errors & Corrections", new_content)

    def log_work(self, entry: str):
        """Add to the worklog."""
        existing = self._read_section("Worklog")
        timestamp = datetime.now().strftime("%H:%M:%S")
        new_entry = f"[{timestamp}] {entry}"
        new_content = existing + "\n" + new_entry if existing else new_entry
        self._update_section("Worklog", new_content)

    def add_learning(self, learning: str):
        """Add a learning to the session."""
        existing = self._read_section("Learnings")
        new_content = existing + "\n- " + learning if existing else "- " + learning
        self._update_section("Learnings", new_content)

    def record_result(self, result: str):
        """Record a key result."""
        existing = self._read_section("Key Results")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"[{timestamp}] {result}"
        new_content = existing + "\n- " + entry if existing else "- " + entry
        self._update_section("Key Results", new_content)

    def should_extract(self) -> bool:
        """Check if both extraction thresholds are met."""
        return (
            self.message_count >= self.MESSAGE_THRESHOLD
            and self.tool_call_count >= self.TOOL_CALL_THRESHOLD
        )

    def increment_message(self):
        """Call this for each user message."""
        self.message_count += 1

    def increment_tool_call(self):
        """Call this for each tool invocation."""
        self.tool_call_count += 1

    def extract_memories(self) -> list[MemoryEntry]:
        """
        Extract typed memories from the session file.
        Returns list of MemoryEntry objects for long-term storage.
        """
        memories = []
        session_content = self._read_full_session()

        # Parse [SAVE_MEMORY] tags from the session
        pattern = r"\[SAVE_MEMORY\s+type=(\w+)\](.*?)\[/SAVE_MEMORY\]"
        matches = re.findall(pattern, session_content, re.DOTALL)

        for mem_type, content in matches:
            if mem_type in ["user", "feedback", "project", "reference"]:
                entry = MemoryEntry(
                    type=mem_type,
                    content=content.strip(),
                    context=self._extract_context(mem_type, content),
                    timestamp=datetime.now().isoformat(),
                    source_session=self.session_id,
                )
                memories.append(entry)

        return memories

    def _read_full_session(self) -> str:
        """Read the entire session file."""
        with open(self.session_path, "r") as f:
            return f.read()

    def _extract_context(self, mem_type: str, content: str) -> str:
        """Extract context based on memory type (why it matters)."""
        contexts = {
            "user": "User preference or background information",
            "feedback": "Correction or confirmation that improves consistency",
            "project": "Ongoing work or architectural decision",
            "reference": "External system or documentation pointer",
        }
        return contexts.get(mem_type, "General context")

    def get_session_summary(self) -> str:
        """Get a quick summary of current session state."""
        current = self._read_section("Current State")
        task = self._read_section("Task Specification")
        return f"Current: {current[:100]}...\nTask: {task[:100]}..."


class MemoryManager:
    """
    Manages long-term memory storage with 4-type taxonomy.
    Stores to user/, feedback/, project/, reference/ subdirectories.
    """

    def __init__(self, base_dir: str = "./memory"):
        self.base_dir = base_dir
        for mem_type in ["user", "feedback", "project", "reference"]:
            os.makedirs(os.path.join(base_dir, mem_type), exist_ok=True)

    def save_memory(self, entry: MemoryEntry):
        """Save a memory entry to the appropriate typed file."""
        filepath = os.path.join(
            self.base_dir, entry.type, f"{entry.source_session or 'global'}.md"
        )

        # Format based on type
        formatted = self._format_entry(entry)

        with open(filepath, "a") as f:
            f.write(formatted + "\n\n")

    def _format_entry(self, entry: MemoryEntry) -> str:
        """Format a memory entry according to its type."""
        timestamp = entry.timestamp[:10]  # Just the date

        if entry.type == "user":
            return f"## {timestamp}\n**Fact:** {entry.content}\n**Why it matters:** {entry.context}"

        elif entry.type == "feedback":
            return f"## {timestamp}\n**Rule:** {entry.content}\n**Why:** {entry.context}\n**Apply:** When similar situation arises"

        elif entry.type == "project":
            return f"## {timestamp}\n**Decision:** {entry.content}\n**Context:** {entry.context}\n**Applies to:** {entry.source_session or 'ongoing'}"

        elif entry.type == "reference":
            return f"## {timestamp}\n**Pointer:** {entry.content}\n**Purpose:** {entry.context}"

        return f"## {timestamp}\n{entry.content}"

    def search_memories(self, query: str, mem_type: Optional[MemoryType] = None) -> list[str]:
        """Simple grep-style search across memories."""
        results = []
        types_to_search = [mem_type] if mem_type else ["user", "feedback", "project", "reference"]

        for mt in types_to_search:
            dir_path = os.path.join(self.base_dir, mt)
            if not os.path.exists(dir_path):
                continue

            for filename in os.listdir(dir_path):
                if filename.endswith(".md"):
                    filepath = os.path.join(dir_path, filename)
                    with open(filepath, "r") as f:
                        content = f.read()
                        if query.lower() in content.lower():
                            # Extract matching section
                            sections = content.split("## ")
                            for section in sections:
                                if query.lower() in section.lower():
                                    results.append(f"[{mt}] {section[:200]}...")

        return results


# Convenience function for inline memory tagging
def save_memory_tag(mem_type: MemoryType, content: str) -> str:
    """
    Returns a tag that the agent can output to mark content for memory.
    The session memory system will extract these on the next consolidation.
    """
    return f"[SAVE_MEMORY type={mem_type}]{content}[/SAVE_MEMORY]"
