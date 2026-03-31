"""
EchoHound v2 — Core Agent Loop
===============================
Enhanced with per-user memory injection and memory-aware responses.

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

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def build_system_prompt(memory_context: str = "", user_name: str = None) -> str:
    """
    Construct the full system prompt with optional memory injection.
    
    Args:
        memory_context: User-specific + community memory to inject
        user_name: User's display name for personalization
    """
    user_line = f"\nYou're chatting with {user_name}." if user_name else ""
    
    return f"""{AGENT_PERSONALITY}{user_line}

When users share information worth remembering (facts, preferences, names, decisions), 
you can signal it by ending your response with [MEMORY: brief summary here].
Be selective — only save genuinely important facts, not every detail.

You have access to tools:
- web_search: Find current information via Brave Search
- web_fetch: Read full web pages and extract content
- file_read: Read files (sandboxed to project directory)
- file_write: Write files (sandboxed)
- exec_command: Run shell commands (requires confirmation)
- memory_read: Read your own memory files

{memory_context}
"""


def run_turn(
    messages: list,
    user_input: str,
    confirm_callback=None,
    memory_context: str = "",
    user_name: str = None,
) -> tuple[str, list]:
    """
    Run a single conversation turn with full agentic tool loop.

    Args:
        messages:         Conversation history (list of {role, content})
        user_input:       The user's message
        confirm_callback: Optional fn(tool_name, tool_input) -> bool
                          Called before CONFIRM_REQUIRED tools.
                          If None, all tools auto-approve (CLI mode).
        memory_context:   Optional memory to inject into system prompt
        user_name:        User's display name for personalization

    Returns:
        (response_text, updated_messages)
    """
    messages = messages + [{"role": "user", "content": user_input}]
    system = build_system_prompt(memory_context, user_name)

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


def cli_confirm(tool_name: str, tool_input: dict) -> bool:
    """Terminal confirmation prompt for sensitive tools."""
    print(f"\n⚠️  {AGENT_NAME} wants to run: {tool_name}")
    print(f"   Input: {json.dumps(tool_input, indent=2)}")
    ans = input("   Allow? [y/N]: ").strip().lower()
    return ans in ("y", "yes")


def run_cli():
    """Interactive CLI mode — chat with EchoHound in your terminal."""
    print(f"\n🐾 {AGENT_NAME} is online. Type 'exit' to quit.\n")
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

        response, messages = run_turn(
            messages,
            user_input,
            confirm_callback=cli_confirm,
        )
        print(f"\n{AGENT_NAME}: {response}\n")


if __name__ == "__main__":
    run_cli()
