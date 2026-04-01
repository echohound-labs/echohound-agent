"""
EchoHound — Telegram Bot
=========================
Connects EchoHound to Telegram so your community can use it
just like the X1 community uses Theo.

Setup:
  1. Message @BotFather on Telegram
  2. /newbot → follow prompts → copy token
  3. Set TELEGRAM_BOT_TOKEN in your .env
  4. python telegram_bot.py

Features:
  - Per-user conversation history (isolated contexts)
  - Group chat support (mention @YourBot to trigger)
  - /start, /help, /memory, /clear commands
  - Rate limiting per user
  - Graceful error handling
"""

import os
import json
import logging
import time
from collections import defaultdict
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import TELEGRAM_BOT_TOKEN, AGENT_NAME
from agent import run_turn, cli_confirm
from memory import read_memory, clear_memory

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Per-user conversation history
# Key: user_id (int), Value: list of message dicts
user_conversations: dict[int, list] = defaultdict(list)

# Simple rate limiting: max N messages per minute per user
RATE_LIMIT = 10
user_message_times: dict[int, list] = defaultdict(list)


def is_rate_limited(user_id: int) -> bool:
    """Return True if user has exceeded rate limit."""
    now = time.time()
    times = user_message_times[user_id]
    # Keep only timestamps within the last 60 seconds
    times = [t for t in times if now - t < 60]
    user_message_times[user_id] = times
    if len(times) >= RATE_LIMIT:
        return True
    times.append(now)
    return False


def auto_approve(tool_name: str, tool_input: dict) -> bool:
    """
    In Telegram bot mode, auto-approve safe tools,
    deny destructive ones without asking.
    """
    ALWAYS_DENY = ["exec_command", "file_delete"]
    if tool_name in ALWAYS_DENY:
        return False
    return True


# ── Command Handlers ──────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🐾 *{AGENT_NAME} is online.*\n\n"
        f"Ask me anything — I'll search the web, read files, and remember what matters.\n\n"
        f"Commands:\n"
        f"/help — show this message\n"
        f"/memory — show what I remember about you\n"
        f"/clear — clear your conversation history\n"
        f"/reset — wipe my memory (use carefully)",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mem = read_memory()
    if not mem.strip():
        await update.message.reply_text("Memory is empty.")
    else:
        # Telegram has a 4096 char message limit
        if len(mem) > 3800:
            mem = mem[-3800:] + "\n[...older entries trimmed]"
        await update.message.reply_text(f"```\n{mem}\n```", parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_conversations[user_id] = []
    await update.message.reply_text("✅ Conversation history cleared. Memory retained.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_conversations[user_id] = []
    clear_memory()
    await update.message.reply_text("⚠️ Full reset complete. Memory wiped.")


# ── Message Handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages from users."""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    text = update.message.text
    chat_type = update.effective_chat.type

    # In groups, only respond when mentioned or replied to
    if chat_type in ("group", "supergroup"):
        bot_username = context.bot.username
        mentioned = f"@{bot_username}" in text
        is_reply_to_bot = (
            update.message.reply_to_message and
            update.message.reply_to_message.from_user and
            update.message.reply_to_message.from_user.username == bot_username
        )
        if not mentioned and not is_reply_to_bot:
            return
        # Strip the mention from the message
        text = text.replace(f"@{bot_username}", "").strip()

    # Rate limit check
    if is_rate_limited(user_id):
        await update.message.reply_text(
            "⏳ Slow down — you're sending too many messages. Try again in a minute."
        )
        return

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing",
    )

    # Get or create conversation history for this user
    messages = user_conversations[user_id]

    try:
        response, updated_messages = run_turn(
            messages,
            text,
            confirm_callback=auto_approve,
        )
        user_conversations[user_id] = updated_messages

        # Telegram message length limit
        if len(response) > 4000:
            # Split into chunks
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error handling message from {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Something went wrong. Try again in a moment."
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your-telegram-bot-token-here":
        print("❌ No Telegram bot token set. Edit config.py or set TELEGRAM_BOT_TOKEN env var.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"🐾 {AGENT_NAME} Telegram bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
