"""
EchoHound v2 — Telegram Bot
=============================
Upgrade from v1:
  - Uses EchoHound class (per-user agent with full KAIROS wiring)
  - Tier-based rate limiting (admin / whitelist / normal / new_user)
  - /xdream  — dream pass summary
  - /xstatus — agent health + compact stats
  - /xrate   — rate limit status
  - All commands use /x prefix to avoid collisions with other bots

Run: python telegram_bot_v2.py
"""

import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN, AGENT_NAME, ADMIN_USER_IDS
from utils.spinner import get_stalled_message, STALL_THRESHOLD_SECONDS
from agent_v2 import EchoHound
from utils.rate_limiter import RateLimiter, get_user_stats

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("echohound.v2")

rate_limiter = RateLimiter()
_agents: dict[int, EchoHound] = {}


def get_agent(uid: int, username: str = "", first_name: str = "") -> EchoHound:
    if uid not in _agents:
        _agents[uid] = EchoHound(user_id=uid, user_name=username, first_name=first_name)
    return _agents[uid]


def auto_approve(tool_name: str, tool_input: dict) -> bool:
    return tool_name not in {"file_delete", "exec_command"}


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🐾 *{AGENT_NAME} v2* online.\n\n"
        f"Sharp, direct, community-first AI. I remember things across conversations.\n\n"
        f"Use `/xhelp` for all commands.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"*{AGENT_NAME} v2 Commands*\n\n"
        "/xhelp — this message\n"
        "/xmemory — view my memory of you\n"
        "/xdream — dream pass summary\n"
        "/xstatus — agent health + stats\n"
        "/xclear — clear conversation history\n"
        "/xreset — wipe all your memory\n"
        "/xrate — check your rate limit\n\n"
        "In groups, mention me or reply to my message.",
        parse_mode="Markdown",
    )


async def cmd_memory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = get_agent(uid).get_memory_display()
    if len(text) > 3800:
        text = text[:3800] + "\n[...trimmed]"
    await update.message.reply_text(f"```\n{text}\n```", parse_mode="Markdown")


async def cmd_dream(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_agent(update.effective_user.id).get_dream_summary())


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        get_agent(update.effective_user.id).status(), parse_mode="Markdown"
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    get_agent(update.effective_user.id).clear_history()
    await update.message.reply_text("Conversation cleared. Long-term memory kept.")


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in _agents:
        _agents[uid].reset_memory()
        del _agents[uid]
    await update.message.reply_text("Memory wiped. Fresh start. 🐾")


async def cmd_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    cid  = update.effective_chat.id
    s    = get_user_stats(uid, cid)
    await update.message.reply_text(
        f"*Rate limit*\nTier: `{s.get('tier','normal')}`\n"
        f"Last min: {s['messages_last_minute']} | Last hr: {s['messages_last_hour']}\n"
        f"Violations: {s['violation_count']}",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user     = update.effective_user
    uid      = user.id
    chat_id  = update.effective_chat.id
    text     = update.message.text
    is_group = update.effective_chat.type in ("group", "supergroup")

    if is_group:
        bot_username = ctx.bot.username
        mentioned    = f"@{bot_username}" in text
        is_reply     = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.username == bot_username
        )
        if not mentioned and not is_reply:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    if not text:
        return

    allowed, msg = rate_limiter.check_rate_limit(uid, chat_id, admin_ids=ADMIN_USER_IDS)
    if not allowed:
        await update.message.reply_text(msg)
        return

    agent = get_agent(uid, user.username or "", user.first_name or "")
    await ctx.bot.send_chat_action(chat_id, "typing")

    response_done = False
    async def _stall_watcher():
        await asyncio.sleep(STALL_THRESHOLD_SECONDS)
        if not response_done:
            await update.message.reply_text(get_stalled_message())
    stall_task = asyncio.create_task(_stall_watcher())

    try:
        response = await agent.chat(text, confirm_callback=auto_approve)
        response_done = True
        stall_task.cancel()
        if len(response) > 4000:
            for chunk in [response[i:i+4000] for i in range(0, len(response), 4000)]:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error for user {uid}: {e}", exc_info=True)
        await update.message.reply_text("Something went wrong. Try again or /xclear.")


async def cmd_cost(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        get_agent(uid).cost.format_summary(), parse_mode="Markdown"
    )


def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your-telegram-bot-token-here":
        print("❌ TELEGRAM_BOT_TOKEN not set. Add to .env")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("xhelp",   cmd_help))
    app.add_handler(CommandHandler("xmemory", cmd_memory))
    app.add_handler(CommandHandler("xdream",  cmd_dream))
    app.add_handler(CommandHandler("xstatus", cmd_status))
    app.add_handler(CommandHandler("xclear",  cmd_clear))
    app.add_handler(CommandHandler("xreset",  cmd_reset))
    app.add_handler(CommandHandler("xrate",   cmd_rate))
    app.add_handler(CommandHandler("xcost",   cmd_cost))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"🐾 {AGENT_NAME} v2 starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
