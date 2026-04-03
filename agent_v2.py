"""
EchoHound v2 — Core Agent
==========================
Wires together everything that was built but never connected:
  - memory/session_memory.py  (KAIROS 9-section template + 4-type taxonomy)
  - memory/user_manager.py    (per-user + community memory)
  - utils/rate_limiter.py     (tier-based rate limiting)
  - tools/*                   (web, files, shell, x1 price)
  - services/auto_dream.py    (nightly consolidation)
  - services/auto_compact.py  (context window management)
  - services/swarm.py         (parallel subagents)
  - services/todo.py          (task tracking + verification nudge)

Architecture inspired by Claude Code source leak — March 31, 2026.
"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Optional

import anthropic

from config import (
    ANTHROPIC_API_KEY, MODEL, MAX_TOKENS,
    AGENT_NAME, AGENT_PERSONALITY,
    CONFIRM_REQUIRED, AUTO_ALLOWED,
)

# ── Memory (already in repo — now actually used) ───────────────────────────────
from memory.session_memory import (
    build_memory_prompt_for_user,
    get_session_memory,
    save_typed_memory,
    should_extract_memory,
    get_memory_update_prompt,
    init_session_memory,
    clear_session_memory,
)
from memory.user_manager import (
    get_user_memory,
    write_user_memory,
    memory_for_prompt,
    clear_user_memory,
)

# ── New services ───────────────────────────────────────────────────────────────
from services.auto_dream import AutoDream, run_dream_scheduler
from services.auto_compact import AutoCompact
from services.swarm import SwarmCoordinator
from services.todo import TodoList, TODO_TOOL_DEFINITIONS

# ── Tools (already in repo) ────────────────────────────────────────────────────
from tools.web_search import web_search
from tools.web_fetch import web_fetch
from tools.file_ops import file_read, file_write, file_list, file_delete
from tools.exec_tool import exec_command
from tools.memory_fts import fts_search, FTS_TOOL_DEFINITION
from tools.x1_price import (
    get_xnt_price, get_token_price, get_xnt_holders, get_gas_stats,
    format_price_response,
    TOOL_DEFINITIONS as X1_TOOL_DEFINITIONS,
    TOOL_MAP as X1_TOOL_MAP,
)

from utils.cost_tracker import CostTracker
from utils.api_retry import create_with_retry
from utils.token_budget import extract_budget_from_message

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DREAM_PASS_EVERY = 5  # run dream memory extraction every N messages

# ── Tool definitions ───────────────────────────────────────────────────────────

CORE_TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the web for current information. Uses Brave Search, falls back to DuckDuckGo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query":   {"type": "string"},
                "count":   {"type": "integer", "default": 5},
                "country": {"type": "string", "default": "US"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch and read a full webpage as clean text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url":       {"type": "string"},
                "max_chars": {"type": "integer", "default": 8000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "file_read",
        "description": "Read a file. Supports line offset and limit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":   {"type": "string"},
                "offset": {"type": "integer", "default": 1},
                "limit":  {"type": "integer", "default": 200},
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_write",
        "description": "Write content to a file (sandboxed).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":      {"type": "string"},
                "content":   {"type": "string"},
                "overwrite": {"type": "boolean", "default": True},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "file_list",
        "description": "List files in a directory. Supports glob patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "default": "."},
                "pattern": {"type": "string", "default": "*"},
            },
        },
    },
    {
        "name": "exec_command",
        "description": "Run a shell command. Requires confirmation for destructive ops.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "memory_save",
        "description": (
            "Save to long-term memory. "
            "IMPORTANT: save CONFIRMATIONS as well as corrections. "
            "When user says 'yes exactly' or 'keep doing that' — save it as feedback. "
            "This is what keeps you consistent across sessions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["user", "feedback", "project", "reference"],
                    "description": "user=who they are | feedback=corrections+confirmations | project=ongoing work | reference=external pointers",
                },
                "content": {
                    "type": "string",
                    "description": "Fact. **Why it matters:** ... **Apply:** when to use. Under 300 chars.",
                },
            },
            "required": ["type", "content"],
        },
    },
    {
        "name": "swarm_spawn",
        "description": "Spawn parallel subagents for independent tasks. Use when work can be parallelized.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of independent task prompts to run in parallel",
                },
                "context": {"type": "string", "description": "Shared context for all subagents"},
            },
            "required": ["subtasks"],
        },
    },
]

ALL_TOOL_DEFINITIONS = CORE_TOOL_DEFINITIONS + TODO_TOOL_DEFINITIONS + X1_TOOL_DEFINITIONS + [FTS_TOOL_DEFINITION]

TOOL_MAP = {
    "web_search":   lambda a: web_search(a.get("query"), a.get("count", 5), a.get("country", "US")),
    "web_fetch":    lambda a: web_fetch(a.get("url"), a.get("max_chars", 8000)),
    "file_read":    lambda a: file_read(a.get("path"), a.get("offset", 1), a.get("limit", 200)),
    "file_write":   lambda a: file_write(a.get("path"), a.get("content"), a.get("overwrite", True)),
    "file_list":    lambda a: file_list(a.get("path", "."), a.get("pattern", "*")),
    "exec_command": lambda a: exec_command(a.get("command"), a.get("timeout", 30)),
    "memory_fts_search": lambda a: fts_search(a.get("query"), a.get("limit", 8), a.get("sender"), a.get("since_days")),
    **X1_TOOL_MAP,
}


def _build_system_prompt(user_id: int, user_name: str = None, chat_id: int = 0) -> str:
    """Build full system prompt with all memory layers injected."""
    parts = [AGENT_PERSONALITY]
    if user_name:
        parts.append(f"\nYou're talking with {user_name}.")

    # KAIROS session memory (Current State first — most important for continuity)
    session_ctx = build_memory_prompt_for_user(user_id)
    if session_ctx:
        parts.append(session_ctx)

    # Per-user + community typed memories
    mem_ctx = memory_for_prompt(user_id, chat_id=chat_id)
    if mem_ctx:
        parts.append(mem_ctx)

    parts.append(
        "\nMemory: use memory_save tool to save facts. "
        "Save CONFIRMATIONS too, not just corrections. "
        "Or tag inline: [SAVE_MEMORY type=feedback]content[/SAVE_MEMORY]"
    )
    parts.append(
        "\nOUTPUT FORMAT — STRICT:\n"
        "You are replying in Telegram. Use plain conversational text only.\n"
        "NEVER use: ** bold **, # headers, --- dividers, or markdown tables.\n"
        "Short paragraphs. No bullet walls. Get to the point fast."
    )

    return "\n".join(parts)


def _process_inline_tags(text: str, user_id: int):
    """Save any [SAVE_MEMORY] tags the agent emitted inline."""
    pattern = r'\[SAVE_MEMORY type=(\w+)\](.*?)\[/SAVE_MEMORY\]'
    for mtype, content in re.findall(pattern, text, re.DOTALL):
        if mtype in ("user", "feedback", "project", "reference"):
            save_typed_memory(user_id, mtype, content.strip())


async def _execute_tool(name, args, user_id, todo=None, swarm=None):
    if name in TOOL_MAP:
        try:
            return TOOL_MAP[name](args)
        except Exception as e:
            return {"error": str(e)}

    if name == "memory_save":
        save_typed_memory(user_id, args["type"], args["content"])
        return {"saved": True, "type": args["type"]}

    if name == "swarm_spawn" and swarm:
        return await swarm.research_swarm(
            args.get("subtasks", []),
            shared_context={"context": args.get("context", "")},
        )

    if todo:
        if name == "todo_add":
            item = todo.add(args["task"], args.get("priority", 1), args.get("is_verification", False))
            return f"Added [{item.id}]: {item.task}" + (todo.get_nudge_message() or "")
        if name == "todo_complete":
            item = todo.complete(args["task_id"], args.get("notes", ""))
            return (f"Done: {item.task}" if item else f"Not found: {args['task_id']}") + (todo.get_nudge_message() or "")
        if name == "todo_in_progress":
            item = todo.set_in_progress(args["task_id"])
            return f"In progress: {item.task}" if item else f"Not found: {args['task_id']}"

    return {"error": f"Unknown tool: {name}"}


# ── EchoHound per-user agent ───────────────────────────────────────────────────

class EchoHound:
    """
    Stateful per-user EchoHound agent.
    One instance per user. Holds conversation + all KAIROS components.
    """

    def __init__(self, user_id: int, user_name: str = "", first_name: str = "", chat_id: int = 0):
        self.user_id   = user_id
        self.chat_id   = chat_id
        self.user_name = user_name or first_name or str(user_id)
        self.messages: list = []

        self._msg_count        = 0
        self._tool_calls       = 0
        self._last_extract_at  = 0
        self._msgs_since_dream = 0
        self._dream_count      = 0

        self.todo        = TodoList(session_id=str(user_id))
        self.autocompact = AutoCompact()
        self._swarm      = SwarmCoordinator(client)

        self.cost = CostTracker()

        init_session_memory(user_id)

    async def chat(self, text: str, confirm_callback=None) -> str:
        budget, text = extract_budget_from_message(text)
        messages = self.messages + [{"role": "user", "content": text}]
        system   = _build_system_prompt(self.user_id, self.user_name, self.chat_id)

        if self.autocompact.should_compact(messages, system):
            messages, _ = await self.autocompact.compact(messages, system)

        tool_call_count = 0

        while True:
            response = await create_with_retry(
                client,
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                tools=ALL_TOOL_DEFINITIONS,
                messages=messages,
            )
            self.cost.add(response.usage, MODEL)

            text_parts, tool_calls = [], []
            for block in response.content:
                if block.type == "text":       text_parts.append(block.text)
                elif block.type == "tool_use": tool_calls.append(block)

            messages.append({"role": "assistant", "content": response.content})

            if not tool_calls:
                final = " ".join(text_parts).strip()
                break

            tool_results = []
            for tc in tool_calls:
                if tc.name in CONFIRM_REQUIRED and confirm_callback:
                    if not confirm_callback(tc.name, tc.input):
                        result = {"error": f"Permission denied for '{tc.name}'"}
                        tool_results.append({"type": "tool_result", "tool_use_id": tc.id, "content": json.dumps(result)})
                        continue
                result = await _execute_tool(tc.name, tc.input, self.user_id, self.todo, self._swarm)
                tool_call_count += 1
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": json.dumps(result) if isinstance(result, dict) else str(result),
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            final = "I got stuck in a loop. Please try again."

        self.messages       = messages
        self._msg_count    += 1
        self._tool_calls   += tool_call_count
        self._msgs_since_dream += 1

        # Process inline memory tags
        _process_inline_tags(final, self.user_id)
        final = re.sub(r'\[SAVE_MEMORY[^\]]*\].*?\[/SAVE_MEMORY\]', '', final, flags=re.DOTALL).strip()
        if not final:
            final = "Done."

        # Background session memory extraction
        if should_extract_memory(self._msg_count, self._tool_calls, self._last_extract_at):
            self._last_extract_at = self._msg_count
            asyncio.create_task(self._background_extract())

        # Dream pass every N messages
        if self._msgs_since_dream >= DREAM_PASS_EVERY:
            self._msgs_since_dream = 0
            asyncio.create_task(self._dream_pass())

        return final

    async def _background_extract(self):
        """Background subagent: update KAIROS session template. Never blocks response."""
        try:
            prompt = get_memory_update_prompt(self.user_id, str(self.user_id))
            resp = await asyncio.to_thread(
                client.messages.create,
                model=MODEL,
                max_tokens=2000,
                messages=[*self.messages[-20:], {"role": "user", "content": prompt}]
            )
            _process_inline_tags(resp.content[0].text, self.user_id)
        except Exception as e:
            print(f"[SessionMemory] Background extract error: {e}")

    async def _dream_pass(self):
        """Every 5 messages: extract typed memories from recent conversation."""
        try:
            conv = "\n".join(
                f"[{m['role'].upper()}]: {str(m.get('content',''))[:300]}"
                for m in self.messages[-30:]
                if isinstance(m.get('content'), str)
            )
            prompt = f"""BACKGROUND TASK — memory extraction. Do not reference this in chat.

Read this conversation and extract any facts worth saving long-term.
Output [SAVE_MEMORY type=user|feedback|project|reference]content[/SAVE_MEMORY] for each.
Save CONFIRMATIONS too — not just corrections.
If nothing worth saving, output nothing.

CONVERSATION:
{conv[:4000]}"""

            resp = await asyncio.to_thread(
                client.messages.create,
                model=MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            _process_inline_tags(resp.content[0].text, self.user_id)
            self._dream_count += 1
        except Exception as e:
            print(f"[DreamPass] Error: {e}")

    # ── Public interface ───────────────────────────────────────────────────────

    def clear_history(self):
        self.messages = []
        self._msg_count = self._tool_calls = 0
        self.cost.reset()

    def reset_memory(self):
        clear_user_memory(self.user_id)
        clear_session_memory(self.user_id)
        self.messages = []

    def get_memory_display(self) -> str:
        user_mem = get_user_memory(self.user_id)
        session  = get_session_memory(self.user_id)
        parts = []
        if user_mem.strip():
            parts.append(f"**Long-term memory:**\n{user_mem[:1500]}")
        if session.strip():
            parts.append(f"**Session notes:**\n{session[:800]}")
        return "\n\n".join(parts) or "(no memories yet)"

    def get_dream_summary(self) -> str:
        return (
            f"Dream passes this session: {self._dream_count}\n"
            f"Next in: {max(0, DREAM_PASS_EVERY - self._msgs_since_dream)} messages"
        )

    def status(self) -> str:
        c = self.autocompact.status()
        return (
            f"**EchoHound v2 Status**\n"
            f"Messages: {self._msg_count} | Tools used: {self._tool_calls}\n"
            f"Dream passes: {self._dream_count} | Next in: {max(0, DREAM_PASS_EVERY - self._msgs_since_dream)} msgs\n"
            f"AutoCompact: {'🔴 circuit broken' if c.get('circuit_open') else '🟢 ok'}\n"
            f"{self.cost.format_summary()}"
        )
