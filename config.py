"""
EchoHound Configuration
=======================
All settings in one place. Set secrets via environment variables — never hardcode.
"""

import os

# ── Anthropic (required) ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-api-key-here")
MAX_TOKENS = 4096

# ── Model Tiers ───────────────────────────────────────────────────────────────
# Switch with /xmodel command (admin only)
# Cost per 1M tokens (approx):
#   Haiku 3.5:  $0.08 in / $0.40 out   ← cheapest, fast, good for simple Q&A
#   Sonnet 4.5: $3.00 in / $15.00 out  ← balanced, default
#   Opus 4:     $15.00 in / $75.00 out ← most capable, expensive
MODELS = {
    "fast":    "claude-haiku-3-5",    # ~40x cheaper than sonnet — for simple tasks
    "default": "claude-sonnet-4-5",   # Best cost/performance balance
    "pro":     "claude-opus-4-5",     # Max capability, reserved for complex tasks
}

# Active model — change this OR set MODEL env var OR use /xmodel command at runtime
MODEL = os.getenv("ECHOHOUND_MODEL", MODELS["default"])

# ── Telegram (required for bot mode) ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your-telegram-bot-token-here")

# ── Optional tools ────────────────────────────────────────────────────────────
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

# ── Memory (KAIROS-style persistence) ────────────────────────────────────────
MEMORY_FILE = "memory/memory.md"
MEMORY_MAX_CHARS = 8000

# ── Admin Users ───────────────────────────────────────────────────────────────
# Telegram user IDs that bypass rate limits + have access to admin commands
ADMIN_USER_IDS = [
    5451495644,  # Skywalker
    # Add more admin IDs here
]

# ── Permissions ───────────────────────────────────────────────────────────────
CONFIRM_REQUIRED = ["exec", "file_write", "file_delete"]
AUTO_ALLOWED = ["web_search", "web_fetch", "file_read", "memory_read"]

# ── Command Prefix ────────────────────────────────────────────────────────────
# All EchoHound commands use /x prefix to avoid collisions with other bots
CMD = "x"  # e.g. /xhelp, /xmemory, /xclear

# ── Personality ───────────────────────────────────────────────────────────────
AGENT_NAME = "EchoHound"
AGENT_PERSONALITY = """
You are EchoHound — a sharp, direct AI agent built for the community.
You cut through noise and get to the point. No fluff, no filler.
You're friendly and approachable but never waste words.
You back up your answers with real data when you can.
When you don't know something, you say so and go find out.
You're loyal to the people using you and treat every question seriously.
"""
