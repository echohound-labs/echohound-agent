"""
EchoHound v2 — Telegram Bot
=============================
Enhanced with per-user memory and advanced rate limiting.

Setup:
  1. Message @BotFather on Telegram
  2. /newbot → follow prompts → copy token
  3. Set TELEGRAM_BOT_TOKEN in your .env
  4. python telegram_bot_v2.py

Features:
  - Per-user conversation history (isolated contexts)
  - Per-user persistent memory (remembers each person)
  - Community memory (shared group knowledge)
  - Tiered rate limiting (new users vs trusted vs whitelisted)
  - Admin commands for moderation
  - Group chat support with mention detection
  - Typing indicators for natural feel
"""

import os
import json
import logging
from collections import defaultdict
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import TELEGRAM_BOT_TOKEN, AGENT_NAME, ADMIN_USER_IDS
from agent import run_turn

# New enhanced systems
from memory.user_manager import (
    get_user_memory,
    write_user_memory,
    clear_user_memory,
    memory_for_prompt,
    get_user_summary,
    get_active_users,
)
from utils.rate_limiter import (
    check_rate_limit,
    get_user_stats,
    get_user_tier,
    whitelist_user,
    unwhitelist_user,
    reset_user,
    RateTier,
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# In-memory conversation cache (not persistent, just for current session)
# Key: "chat_id:user_id", Value: list of message dicts
user_conversations: dict[str, list] = defaultdict(list)


def _get_convo_key(chat_id: int, user_id: int) -> str:
    """Create unique key for conversation isolation."""
    return f"{chat_id}:{user_id}"


def auto_approve(tool_name: str, tool_input: dict) -> bool:
    """
    In Telegram bot mode, auto-approve safe tools,
    deny destructive ones without asking.
    """
    ALWAYS_DENY = ["exec_command", "file_delete", "file_write"]
    if tool_name in ALWAYS_DENY:
        return False
    return True


# ── Command Handlers ──────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with user-specific context."""
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    
    # Get user stats
    stats = get_user_stats(user_id, chat_id)
    tier = stats.get("tier", "normal")
    
    # Get their memory
    user_mem = get_user_memory(user_id)
    
    msg = f"🐾 *{AGENT_NAME} is online.*\n\n"
    
    # Personalized welcome if they have history
    if user_mem and "first_seen" in user_mem:
        msg += f"Welcome back! I've been tracking your info.\n\n"
    else:
        msg += f"Hey {user.first_name or 'there'}! Nice to meet you.\n\n"
    
    msg += (
        f"I'm a community AI agent — I can search the web, remember our "
        f"conversations, and help with anything you need.\n\n"
        f"*Commands:*\n"
        f"/help — Show all commands\n"
        f"/memory — What I remember about you\n"
        f"/status — Your rate limit status\n"
        f"/clear — Clear this conversation\n"
        f"/reset — Wipe my memory of you\n"
    )
    
    # Show admin commands if applicable
    if user_id in ADMIN_USER_IDS:
        msg += (
            f"\n*Admin Commands:*\n"
            f"/whitelist @username — Bypass rate limits\n"
            f"/unwhitelist @username — Remove whitelist\n"
            f"/stats — Show bot stats\n"
            f"/broadcast — Message all users\n"
        )
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed help message."""
    user = update.effective_user
    
    msg = (
        f"🐾 *{AGENT_NAME} Commands*\n\n"
        f"*Basic:*\n"
        f"• Just message me — I'll remember our conversation\n"
        f"• In groups, mention me or reply to my messages\n\n"
        f"*Commands:*\n"
        f"`/start` — Welcome message\n"
        f"`/help` — This help text\n"
        f"`/memory` — What I remember about you\n"
        f"`/status` — Your rate limit tier and stats\n"
        f"`/clear` — Clear current conversation (keeps memory)\n"
        f"`/reset` — Wipe all my memory of you\n"
    )
    
    if user.id in ADMIN_USER_IDS:
        msg += (
            f"\n*Admin:*\n"
            f"`/whitelist @username` — Whitelist user\n"
            f"`/unwhitelist @username` — Remove whitelist\n"
            f"`/stats` — Bot usage statistics\n"
            f"`/broadcast message` — Message all active users\n"
        )
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show what EchoHound remembers about this user."""
    user_id = update.effective_user.id
    
    mem = get_user_memory(user_id)
    summary = get_user_summary(user_id)
    
    if not mem.strip() or mem.strip() == "# EchoHound Memory":
        await update.message.reply_text(
            "🤔 I don't have any memories saved about you yet. "
            "Start chatting and I'll remember what matters!"
        )
        return
    
    msg = f"🧠 *What I remember:*\n\n{summary}\n\n```\n{mem[:3500]}\n```"
    
    if len(mem) > 3500:
        msg += "\n[...older memories available in full file]"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's rate limit status."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    stats = get_user_stats(user_id, chat_id)
    tier = stats.get("tier", "normal")
    
    tier_emoji = {
        "whitelisted": "✅",
        "admin": "👑",
        "normal": "👤",
        "new_user": "🆕",
        "rate_limited": "⏳",
    }.get(tier, "👤")
    
    msg = (
        f"📊 *Your Status*\n\n"
        f"Tier: {tier_emoji} {tier.upper()}\n"
        f"Messages (last hour): {stats.get('messages_last_hour', 0)}\n"
        f"Messages (last day): {stats.get('messages_last_day', 0)}\n"
    )
    
    if tier == "new_user":
        msg += "\n_You're in the new user tier (first 24h). Limits: 5/min, 20/hour_"
    elif tier == "rate_limited":
        msg += "\n⚠️ _You're temporarily rate limited. Wait for cooldown._"
    elif tier == "normal":
        msg += "\n_Limits: 10/min, 50/hour. Stay cool and don't spam!_"
    elif tier in ["whitelisted", "admin"]:
        msg += "\n✨ _No rate limits applied. Trusted user._"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear current conversation (memory retained)."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    convo_key = _get_convo_key(chat_id, user_id)
    user_conversations[convo_key] = []
    
    await update.message.reply_text(
        "✅ Conversation cleared. *Memory retained.*\n\n"
        "I still remember what we've discussed — this just clears the "
        "current chat session.",
        parse_mode="Markdown",
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wipe all memory for this user."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Clear conversation
    convo_key = _get_convo_key(chat_id, user_id)
    user_conversations[convo_key] = []
    
    # Clear persistent memory
    clear_user_memory(user_id)
    
    # Clear rate limit data too
    reset_user(user_id, chat_id)
    
    await update.message.reply_text(
        "⚠️ *Full reset complete.*\n\n"
        "All memory wiped. It's like we never met. 👋",
        parse_mode="Markdown",
    )


# ── Admin Commands ────────────────────────────────────────────────────────────

async def whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: whitelist a user."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    if user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin only.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /whitelist @username")
        return
    
    # In a real implementation, you'd lookup user_id from username
    # For now, placeholder
    await update.message.reply_text(
        "⚠️ Whitelist by replying to a user's message with /whitelist"
    )


async def unwhitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: remove user from whitelist."""
    user = update.effective_user
    
    if user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin only.")
        return
    
    await update.message.reply_text("Reply to a user message with /unwhitelist")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: show bot statistics."""
    user = update.effective_user
    
    if user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin only.")
        return
    
    active_today = get_active_users(days=1)
    active_week = get_active_users(days=7)
    
    msg = (
        f"📈 *Bot Statistics*\n\n"
        f"Active users (24h): {len(active_today)}\n"
        f"Active users (7d): {len(active_week)}\n\n"
        f"_Rate limit data stored per chat:user_"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── Message Handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages from users."""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    chat_type = update.effective_chat.type
    
    # Get user name for memory
    user_name = user.username or user.first_name or f"User_{user_id}"

    # In groups, only respond when mentioned or replied to
    if chat_type in ("group", "supergroup"):
        bot_username = context.bot.username
        mentioned = f"@{bot_username}" in text
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.username == bot_username
        )
        if not mentioned and not is_reply_to_bot:
            return
        # Strip the mention from the message
        text = text.replace(f"@{bot_username}", "").strip()

    # Rate limit check
    allowed, rate_msg = check_rate_limit(user_id, chat_id, ADMIN_USER_IDS)
    if not allowed:
        await update.message.reply_text(rate_msg, parse_mode="Markdown")
        return

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing",
    )

    # Get or create conversation history for this user
    convo_key = _get_convo_key(chat_id, user_id)
    messages = user_conversations[convo_key]
    
    # Inject memory into system prompt
    memory_context = memory_for_prompt(user_id)

    try:
        # Run the agent turn with memory injection
        response, updated_messages = run_turn(
            messages,
            text,
            confirm_callback=auto_approve,
            memory_context=memory_context,
            user_name=user_name,
        )
        user_conversations[convo_key] = updated_messages
        
        # Check if agent wants to save something to memory
        # (This would be implemented in agent.py - for now, simple regex check)
        if "[MEMORY:" in response:
            # Extract memory entry
            import re
            mem_match = re.search(r'\[MEMORY:([^\]]+)\]', response)
            if mem_match:
                mem_entry = mem_match.group(1).strip()
                write_user_memory(user_id, mem_entry, user_name)
                # Remove the [MEMORY:...] from response
                response = re.sub(r'\[MEMORY:[^\]]+\]', '', response).strip()

        # Telegram message length limit
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error handling message from {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Something went wrong on my end. Try again in a moment."
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your-telegram-bot-token-here":
        print("❌ No Telegram bot token set. Set TELEGRAM_BOT_TOKEN env var.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("reset", reset_command))
    
    # Admin handlers
    app.add_handler(CommandHandler("whitelist", whitelist_command))
    app.add_handler(CommandHandler("unwhitelist", unwhitelist_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"🐾 {AGENT_NAME} v2 Telegram bot starting...")
    print(f"   Rate limiting: ENABLED (tiered system)")
    print(f"   Per-user memory: ENABLED")
    print(f"   Community memory: ENABLED")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
