"""
EchoHound v2 — Telegram Bot
=============================
All commands prefixed with /x to avoid collisions with other bots.
  /xstart  /xhelp  /xmemory  /xstatus  /xclear  /xreset
  /xmodel  (admin) — switch model tier on the fly
  /xwhitelist /xstats (admin)

Setup:
  1. Set env vars: TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY
  2. python telegram_bot_v2.py
"""

import os
import logging
from collections import defaultdict
import config  # mutable reference so live model swaps work

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from agent_v2 import run_turn
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
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Per-user conversation cache (current session only)
user_conversations: dict[str, list] = defaultdict(list)


def _key(chat_id: int, user_id: int) -> str:
    return f"{chat_id}:{user_id}"


def auto_approve(tool_name: str, tool_input: dict) -> bool:
    DENY = {"exec_command", "file_delete", "file_write"}
    return tool_name not in DENY


# ── /xstart ──────────────────────────────────────────────────────────────────

async def xstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    user_mem = get_user_memory(user_id)

    if user_mem.strip():
        greeting = f"Welcome back, {user.first_name or 'anon'}!"
    else:
        greeting = f"Hey {user.first_name or 'anon'}! Nice to meet you."

    admin_note = ""
    if user_id in config.ADMIN_USER_IDS:
        admin_note = "\n\n*Admin commands:* /xmodel /xwhitelist /xstats"

    msg = (
        f"🐾 *EchoHound is online.*\n\n"
        f"{greeting}\n\n"
        f"Mention me or reply to my messages and I'll respond.\n\n"
        f"*Commands:*\n"
        f"`/xhelp` — all commands\n"
        f"`/xmemory` — what I remember about you\n"
        f"`/xstatus` — your rate limit tier\n"
        f"`/xclear` — clear conversation\n"
        f"`/xreset` — wipe your data"
        f"{admin_note}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── /xhelp ───────────────────────────────────────────────────────────────────

async def xhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    model_tier = "default"
    for tier, model_id in config.MODELS.items():
        if model_id == config.MODEL:
            model_tier = tier
            break

    msg = (
        f"🐾 *EchoHound Commands*\n\n"
        f"*User:*\n"
        f"`/xstart` — welcome\n"
        f"`/xhelp` — this list\n"
        f"`/xmemory` — what I remember about you\n"
        f"`/xstatus` — your rate limit tier & usage\n"
        f"`/xclear` — clear this conversation (keeps memory)\n"
        f"`/xreset` — wipe all your data\n\n"
        f"*Current model:* `{model_tier}` (`{config.MODEL}`)\n"
    )

    if user.id in config.ADMIN_USER_IDS:
        msg += (
            f"\n*Admin:*\n"
            f"`/xmodel fast|default|pro` — switch model\n"
            f"`/xwhitelist` — reply to user + run to whitelist them\n"
            f"`/xunwhitelist` — remove whitelist\n"
            f"`/xstats` — bot usage stats\n"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


# ── /xmemory ─────────────────────────────────────────────────────────────────

async def xmemory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mem = get_user_memory(user_id)
    summary = get_user_summary(user_id)

    if not mem.strip():
        await update.message.reply_text(
            "🤔 Nothing saved yet. Chat with me and I'll start remembering what matters."
        )
        return

    text = f"🧠 *Your Memory File*\n_{summary}_\n\n```\n{mem[:3400]}\n```"
    if len(mem) > 3400:
        text += "\n_[older entries trimmed for display]_"

    await update.message.reply_text(text, parse_mode="Markdown")


# ── /xstatus ─────────────────────────────────────────────────────────────────

async def xstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    stats = get_user_stats(user_id, chat_id)
    tier = stats.get("tier", "normal")

    emoji = {
        "whitelisted": "✅", "admin": "👑",
        "normal": "👤", "new_user": "🆕", "rate_limited": "⏳",
    }.get(tier, "👤")

    notes = {
        "new_user":     "_New user tier (first 24h): 5/min, 20/hour_",
        "rate_limited": "⚠️ _Temporarily rate limited. Wait for cooldown._",
        "normal":       "_Standard limits: 10/min, 50/hour_",
        "whitelisted":  "✨ _Trusted user — no limits_",
        "admin":        "👑 _Admin — no limits_",
    }.get(tier, "")

    model_tier = "default"
    for t, m in config.MODELS.items():
        if m == config.MODEL:
            model_tier = t

    msg = (
        f"📊 *Your Status*\n\n"
        f"Tier: {emoji} `{tier.upper()}`\n"
        f"Messages (last min): {stats.get('messages_last_minute', 0)}\n"
        f"Messages (last hr): {stats.get('messages_last_hour', 0)}\n"
        f"Messages (today): {stats.get('messages_last_day', 0)}\n"
        f"Violations: {stats.get('violation_count', 0)}\n"
        f"First seen: {stats.get('first_seen', 'Unknown')}\n\n"
        f"Active model: `{model_tier}` — `{config.MODEL}`\n\n"
        f"{notes}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── /xclear ──────────────────────────────────────────────────────────────────

async def xclear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_conversations[_key(chat_id, user_id)] = []
    await update.message.reply_text(
        "✅ Conversation cleared. *Your memory is kept.*",
        parse_mode="Markdown",
    )


# ── /xreset ──────────────────────────────────────────────────────────────────

async def xreset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_conversations[_key(chat_id, user_id)] = []
    clear_user_memory(user_id)
    reset_user(user_id, chat_id)
    await update.message.reply_text(
        "⚠️ *Full reset.* Memory wiped. We've never met. 👋",
        parse_mode="Markdown",
    )


# ── /xmodel (admin) ───────────────────────────────────────────────────────────

async def xmodel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch active model tier on the fly. Admin only."""
    user = update.effective_user
    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin only.")
        return

    valid_tiers = list(config.MODELS.keys())

    if not context.args or context.args[0] not in valid_tiers:
        lines = [f"`{t}` — `{m}`" for t, m in config.MODELS.items()]
        current = next((t for t, m in config.MODELS.items() if m == config.MODEL), "?")
        await update.message.reply_text(
            f"*Model Tiers:*\n\n" + "\n".join(lines) +
            f"\n\n*Current:* `{current}`\n\n"
            f"Usage: `/xmodel fast|default|pro`",
            parse_mode="Markdown",
        )
        return

    tier = context.args[0]
    config.MODEL = config.MODELS[tier]  # live swap — no restart needed

    cost_note = {
        "fast":    "~40x cheaper than default. Great for simple Q&A.",
        "default": "Balanced cost/performance. The sweet spot.",
        "pro":     "⚠️ Most expensive. Use for complex tasks only.",
    }.get(tier, "")

    await update.message.reply_text(
        f"✅ *Model switched to `{tier}`*\n\n"
        f"Now using: `{config.MODEL}`\n\n"
        f"_{cost_note}_",
        parse_mode="Markdown",
    )
    logger.info(f"Model switched to {tier} ({config.MODEL}) by {user.id}")


# ── /xwhitelist (admin) ───────────────────────────────────────────────────────

async def xwhitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Whitelist a user by replying to their message."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin only.")
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(
            "Reply to a user's message and run `/xwhitelist` to whitelist them.",
            parse_mode="Markdown",
        )
        return

    target_id = reply.from_user.id
    target_name = reply.from_user.username or reply.from_user.first_name
    whitelist_user(target_id, chat_id)

    await update.message.reply_text(
        f"✅ *{target_name}* (`{target_id}`) is now whitelisted.\n"
        f"No rate limits apply.",
        parse_mode="Markdown",
    )


# ── /xunwhitelist (admin) ─────────────────────────────────────────────────────

async def xunwhitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove whitelist by replying to a message."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin only.")
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text("Reply to a user's message and run `/xunwhitelist`.")
        return

    target_id = reply.from_user.id
    target_name = reply.from_user.username or reply.from_user.first_name
    unwhitelist_user(target_id, chat_id)

    await update.message.reply_text(
        f"✅ *{target_name}* removed from whitelist. Standard limits apply.",
        parse_mode="Markdown",
    )


# ── /xstats (admin) ───────────────────────────────────────────────────────────

async def xstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("❌ Admin only.")
        return

    active_today = get_active_users(days=1)
    active_week = get_active_users(days=7)
    current_tier = next((t for t, m in config.MODELS.items() if m == config.MODEL), "?")

    msg = (
        f"📈 *EchoHound Stats*\n\n"
        f"Active users (24h): `{len(active_today)}`\n"
        f"Active users (7d): `{len(active_week)}`\n\n"
        f"Active model: `{current_tier}` — `{config.MODEL}`\n"
        f"Max tokens: `{config.MAX_TOKENS}`\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── Message Handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    chat_type = update.effective_chat.type
    user_name = user.username or user.first_name or f"User_{user_id}"

    # Groups: only respond when mentioned or replied to
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
        text = text.replace(f"@{bot_username}", "").strip()

    # Rate limit check
    allowed, rate_msg = check_rate_limit(user_id, chat_id, config.ADMIN_USER_IDS)
    if not allowed:
        await update.message.reply_text(rate_msg)
        return

    # Typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    convo_key = _key(chat_id, user_id)
    messages = user_conversations[convo_key]
    memory_context = memory_for_prompt(user_id)

    try:
        response, updated_messages = run_turn(
            messages,
            text,
            confirm_callback=auto_approve,
            memory_context=memory_context,
            user_name=user_name,
        )
        user_conversations[convo_key] = updated_messages

        # Extract and save any [MEMORY:...] tags the agent embeds
        import re
        for match in re.finditer(r'\[MEMORY:([^\]]+)\]', response):
            write_user_memory(user_id, match.group(1).strip(), user_name)
        response = re.sub(r'\[MEMORY:[^\]]+\]', '', response).strip()

        # Chunk if over Telegram's 4096 limit
        if len(response) > 4000:
            for chunk in [response[i:i+4000] for i in range(0, len(response), 4000)]:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("❌ Something went wrong. Try again in a moment.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your-telegram-bot-token-here":
        print("❌ No TELEGRAM_BOT_TOKEN set.")
        return

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # User commands (/x prefix)
    app.add_handler(CommandHandler("xstart",        xstart))
    app.add_handler(CommandHandler("xhelp",         xhelp))
    app.add_handler(CommandHandler("xmemory",       xmemory))
    app.add_handler(CommandHandler("xstatus",       xstatus))
    app.add_handler(CommandHandler("xclear",        xclear))
    app.add_handler(CommandHandler("xreset",        xreset))

    # Admin commands (/x prefix)
    app.add_handler(CommandHandler("xmodel",        xmodel))
    app.add_handler(CommandHandler("xwhitelist",    xwhitelist))
    app.add_handler(CommandHandler("xunwhitelist",  xunwhitelist))
    app.add_handler(CommandHandler("xstats",        xstats))

    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    current_tier = next((t for t, m in config.MODELS.items() if m == config.MODEL), "?")
    print(f"🐾 {config.AGENT_NAME} v2 starting...")
    print(f"   Model:        {current_tier} ({config.MODEL})")
    print(f"   Rate limits:  ENABLED (tiered)")
    print(f"   User memory:  ENABLED")
    print(f"   Commands:     /x prefix (no collisions)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
