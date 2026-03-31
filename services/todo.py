"""
TodoWrite — Task tracking baked into the agentic loop.
Verification nudge: complete 3+ tasks without a verify step → reminder fires.
"""
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from config import SESSIONS_DIR

VERIFY_NUDGE_AFTER = 3
VERIFY_KEYWORDS    = {"verify","check","confirm","test","validate","review","ensure","assert","inspect"}


class TodoStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    DONE        = "done"
    BLOCKED     = "blocked"


@dataclass
class TodoItem:
    id:              str
    task:            str
    status:          TodoStatus = TodoStatus.PENDING
    priority:        int        = 1
    is_verification: bool       = False
    created_at:      float      = field(default_factory=time.time)
    completed_at:    Optional[float] = None
    notes:           str        = ""

    def to_dict(self) -> dict:
        return {**self.__dict__, "status": self.status.value}

    @classmethod
    def from_dict(cls, d: dict) -> "TodoItem":
        d = d.copy(); d["status"] = TodoStatus(d["status"]); return cls(**d)


class TodoList:
    def __init__(self, session_id: str):
        self._file  = SESSIONS_DIR / f"{session_id}_todos.json"
        self._items: list[TodoItem] = []
        self._completed_since_verify = 0
        self._load()

    def _load(self):
        if self._file.exists():
            data = json.loads(self._file.read_text())
            self._items = [TodoItem.from_dict(d) for d in data.get("items", [])]
            self._completed_since_verify = data.get("completed_since_verify", 0)

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps({
            "items": [i.to_dict() for i in self._items],
            "completed_since_verify": self._completed_since_verify,
        }, indent=2))

    def _is_verify(self, task: str) -> bool:
        return any(w in task.lower().split() for w in VERIFY_KEYWORDS)

    def add(self, task: str, priority: int = 1, is_verification: bool = False) -> TodoItem:
        item = TodoItem(
            id=f"todo_{len(self._items)+1}_{int(time.time())}",
            task=task, priority=priority,
            is_verification=is_verification or self._is_verify(task),
        )
        self._items.append(item); self._save(); return item

    def complete(self, task_id: str, notes: str = "") -> Optional[TodoItem]:
        item = self._get(task_id)
        if item:
            item.status = TodoStatus.DONE
            item.completed_at = time.time()
            item.notes = notes
            if item.is_verification:
                self._completed_since_verify = 0
            else:
                self._completed_since_verify += 1
            self._save()
        return item

    def set_in_progress(self, task_id: str) -> Optional[TodoItem]:
        item = self._get(task_id)
        if item: item.status = TodoStatus.IN_PROGRESS; self._save()
        return item

    def _get(self, task_id: str) -> Optional[TodoItem]:
        for i in self._items:
            if i.id == task_id or i.task[:30] == task_id[:30]:
                return i
        return None

    def get_nudge_message(self) -> Optional[str]:
        if self._completed_since_verify >= VERIFY_NUDGE_AFTER:
            pending = sum(1 for i in self._items if i.status == TodoStatus.PENDING)
            return (
                f"\n⚠️ {self._completed_since_verify} tasks done without a verification step. "
                f"Add a verify/check task before finishing. ({pending} still pending)"
            )
        return None

    def render(self) -> str:
        if not self._items: return ""
        icons = {TodoStatus.IN_PROGRESS:"🔄", TodoStatus.PENDING:"⬜", TodoStatus.DONE:"✅", TodoStatus.BLOCKED:"🚫"}
        lines = ["**Tasks**"]
        for item in sorted(self._items, key=lambda x: x.priority):
            v = " [VERIFY]" if item.is_verification else ""
            lines.append(f"{icons[item.status]} [{item.id}] {item.task}{v}")
        nudge = self.get_nudge_message()
        if nudge: lines.append(nudge)
        return "\n".join(lines)


TODO_TOOL_DEFINITIONS = [
    {
        "name": "todo_add",
        "description": "Add a task to the todo list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task":            {"type": "string"},
                "priority":        {"type": "integer", "enum": [1,2,3], "description": "1=high, 2=medium, 3=low"},
                "is_verification": {"type": "boolean", "description": "Is this a verify/check step?"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "todo_complete",
        "description": "Mark a task as done.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "notes":   {"type": "string"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "todo_in_progress",
        "description": "Mark a task as in progress.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
]
