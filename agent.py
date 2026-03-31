"""
EchoHound — Core Agent Loop
============================
The brain. Handles:
  - Conversation management
  - Tool use (agentic loop)
  - Memory injection + writing
  - Permission checks before sensitive tool calls

Architecture inspired by Claude Code's leaked source (March 31, 2026).
"""

import json
import anthropic
from config import (
    ANTHROPIC_API_KEY, MODEL, MAX_TOKENS,
    AGENT_NAME, AGENT_PERSONALITY,
    CONFIRM_REQUIRED, AUTO_ALLOWED,
)
from tools import TOOL_DEFINITIONS, TOOL_MAP
from memory import read_memory, write_memory, memory_summary_prompt

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def build_system_prompt() -> str:
    """Construct the full system prompt with injected memory."""
    memory = read_memory()
    memory_block = memory_summary_prompt(memory)
    return f"{AGENT_PERSONALITY}{memory_block}"


def run_turn(
    messages: list,
    user_input: str,
    confirm_callback=None,
) -> tuple[str, list]:
    """
    Run a single conversation turn with full agentic tool loop.

    Args:
        messages:         Conversation history (list of {role, content})
        user_input:       The user's message
        confirm_callback: Optional fn(tool_name, tool_input) -> bool
                          Called before CONFIRM_REQUIRED tools.
                          If None, all tools auto-approve (CLI mode).

    Returns:
        (response_text, updated_messages)
    """
    messages = messages + [{"role": "user", "content": user_input}]
    system = build_system_prompt()

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Collect text and tool use blocks
        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        # If no tool calls — we're done
        if response.stop_reason == "end_turn" or not tool_calls:
            final_text = " ".join(text_parts).strip()
            messages.append({"role": "assistant", "content": response.content})

            # Auto-extract and save anything worth remembering
            _maybe_save_memory(user_input, final_text)

            return final_text, messages

        # Process tool calls
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for tool_call in tool_calls:
            tool_name = tool_call.name
            tool_input = tool_call.input

            # Permission check
            if tool_name in CONFIRM_REQUIRED and confirm_callback:
                approved = confirm_callback(tool_name, tool_input)
                if not approved:
                    result = {"error": f"User denied permission to run '{tool_name}'"}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps(result),
                    })
                    continue

            # Execute tool
            if tool_name in TOOL_MAP:
                try:
                    result = TOOL_MAP[tool_name](**tool_input)
                except Exception as e:
                    result = {"error": f"Tool execution failed: {str(e)}"}
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": json.dumps(result),
            })

        # Feed tool results back and loop
        messages.append({"role": "user", "content": tool_results})


def _maybe_save_memory(user_input: str, response: str) -> None:
    """
    Simple heuristic: save exchanges that contain facts, names, decisions.
    In production you'd ask Claude itself to decide what's worth remembering
    (the 'dream' consolidation pass from the leaked source).
    """
    keywords = ["remember", "my name is", "i am", "we decided", "important",
                 "always", "never", "prefer", "don't", "make sure"]
    combined = (user_input + " " + response).lower()
    if any(kw in combined for kw in keywords):
        entry = f"User said: {user_input[:200]}\nAgent responded: {response[:300]}"
        write_memory(entry)


# ── CLI Mode ──────────────────────────────────────────────────────────────────

def cli_confirm(tool_name: str, tool_input: dict) -> bool:
    """Terminal confirmation prompt for sensitive tools."""
    print(f"\n⚠️  {AGENT_NAME} wants to run: {tool_name}")
    print(f"   Input: {json.dumps(tool_input, indent=2)}")
    ans = input("   Allow? [y/N]: ").strip().lower()
    return ans in ("y", "yes")


def run_cli():
    """Interactive CLI mode — chat with EchoHound in your terminal."""
    print(f"\n🐾 {AGENT_NAME} is online. Type 'exit' to quit, 'memory' to view memory.\n")
    messages = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            break
        if user_input.lower() == "memory":
            print("\n" + read_memory() + "\n")
            continue

        response, messages = run_turn(
            messages,
            user_input,
            confirm_callback=cli_confirm,
        )
        print(f"\n{AGENT_NAME}: {response}\n")


if __name__ == "__main__":
    run_cli()
