"""
EchoHound Configuration
=======================
Copy this file to config_local.py and fill in your keys.
Never commit config_local.py to GitHub.
"""

import os

# ── Anthropic (required) ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-api-key-here")
MODEL = "claude-sonnet-4-5"          # Sonnet = best cost/performance balance
MAX_TOKENS = 4096

# ── Telegram (required for bot mode) ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your-telegram-bot-token-here")

# ── Optional tools ────────────────────────────────────────────────────────────
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")          # Web search
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")        # Fallback / image gen

# ── Memory (KAIROS-style persistence) ────────────────────────────────────────
MEMORY_FILE = "memory/memory.md"
MEMORY_MAX_CHARS = 8000              # Trim older entries beyond this

# ── Permissions ───────────────────────────────────────────────────────────────
# Tools that require explicit user confirmation before running
CONFIRM_REQUIRED = ["exec", "file_write", "file_delete"]
# Tools always allowed without confirmation
AUTO_ALLOWED = ["web_search", "web_fetch", "file_read", "memory_read"]

# ── Personality (EchoHound soul) ──────────────────────────────────────────────
AGENT_NAME = "EchoHound"
AGENT_PERSONALITY = """
You are EchoHound — a sharp, direct AI agent built for the community.
You cut through noise and get to the point. No fluff, no filler.
You're friendly and approachable but never waste words.
You back up your answers with real data when you can.
When you don't know something, you say so and go find out.
You're loyal to the people using you and treat every question seriously.
"""
