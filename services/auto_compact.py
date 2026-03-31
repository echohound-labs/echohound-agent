"""
AutoCompact — Context Window Management
Fires at ~87% context window usage. Leaves 13K token buffer.
Circuit-breaks after 3 consecutive failures.
"""
import asyncio
import time
from config import ANTHROPIC_API_KEY, MODEL

MODEL_CONTEXT_WINDOWS = {
    "claude-sonnet-4-5": 200_000,
    "claude-haiku-3-5":  200_000,
    "claude-opus-4-5":   200_000,
}
COMPACT_THRESHOLD    = 0.87
BUFFER_TOKENS        = 13_000
MAX_FAILURES         = 3

COMPACT_PROMPT = """\
Summarize this conversation into a dense context summary that preserves:
1. All decisions made
2. All facts gathered
3. Current task state and what still needs doing
4. Any errors and how they were resolved
5. User preferences observed

This replaces the conversation history. Make it complete enough to continue seamlessly.

CONVERSATION:
{conversation}

Start with "## Compacted Context"."""


def _estimate_tokens(messages: list, system: str = "") -> int:
    total = len(system)
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(str(block))
    return total // 4


def _messages_to_text(messages: list) -> str:
    lines = []
    for m in messages:
        role    = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, list):
            parts = []
            for b in content:
                if isinstance(b, dict):
                    if b.get("type") == "text":
                        parts.append(b["text"])
                    elif b.get("type") == "tool_use":
                        parts.append(f"[TOOL: {b['name']}]")
                    elif b.get("type") == "tool_result":
                        parts.append(f"[RESULT: {str(b.get('content',''))[:200]}]")
            content = " ".join(parts)
        lines.append(f"[{role.upper()}]: {content}")
    return "\n".join(lines)


class AutoCompact:
    def __init__(self, model: str = None):
        self.model          = model or MODEL
        self.context_window = MODEL_CONTEXT_WINDOWS.get(self.model, 200_000)
        self._failures      = 0
        self._circuit_open  = False
        self._total_runs    = 0

    def should_compact(self, messages: list, system: str = "") -> bool:
        if self._circuit_open:
            return False
        tokens = _estimate_tokens(messages, system)
        return tokens / self.context_window >= COMPACT_THRESHOLD

    async def compact(self, messages: list, system: str = "") -> tuple[list, bool]:
        if self._circuit_open:
            return messages, False
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
            conv_text = _messages_to_text(messages)
            prompt    = COMPACT_PROMPT.format(conversation=conv_text[:50_000])
            response  = await client.messages.create(
                model=self.model, max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = response.content[0].text.strip()
            new_messages = [
                {"role": "user",      "content": f"[Context compacted at {time.ctime()}]\n\n{summary}\n\nPlease continue."},
                {"role": "assistant", "content": "Understood. Continuing from compacted context."},
            ]
            self._failures   = 0
            self._total_runs += 1
            return new_messages, True
        except Exception as e:
            self._failures += 1
            print(f"[AutoCompact] Failure #{self._failures}: {e}")
            if self._failures >= MAX_FAILURES:
                self._circuit_open = True
                print("[AutoCompact] Circuit breaker OPEN")
            return messages, False

    def status(self) -> dict:
        return {
            "circuit_open":  self._circuit_open,
            "failures":      self._failures,
            "total_runs":    self._total_runs,
            "threshold_pct": int(COMPACT_THRESHOLD * 100),
        }
