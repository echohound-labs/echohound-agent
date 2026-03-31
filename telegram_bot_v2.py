"""
Telegram Bot v2 for EchoHound
With /x commands and Claude Code-style session memory
"""

import os
import re
import json
import logging
import anthropic
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from memory import SessionMemory, MemoryManager, UserManager
from utils import RateLimiter
from tools import get_xnt_price

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_MODEL = "claude-sonnet-4-6"

# Available models
MODELS = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5",
}

# Initialize components
memory_manager = MemoryManager()
user_manager = UserManager()
rate_limiter = RateLimiter()


def get_user_id(update: Update) -> str:
    """Extract user ID from update."""
    if update.effective_user:
        return str(update.effective_user.id)
    return "unknown"


def get_session_id(update: Update) -> str:
    """Generate a session ID for this conversation."""
    user_id = get_user_id(update)
    chat_id = str(update.effective_chat.id) if update.effective_chat else "dm"
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"{user_id}_{chat_id}_{date_str}"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = get_user_id(update)
    user_manager.update_activity(user_id)

    welcome_text = """🐾 **EchoHound is online.**

Sharp, direct, community-first AI — powered by Claude.

**Quick commands:**
• /help — Show all commands
• /memory — View my memory of you
• /xnt — Get current XNT price
• /model — Switch Claude model
• /clear — Clear this conversation

Mention me in groups with @echohound_bot or reply to my messages.
"""

    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """🐾 **EchoHound Commands**

**Core:**
• /start — Introduction
• /help — This message
• /status — Check your rate limit status

**Memory:**
• /memory — View my memory of you
• /clear — Clear current conversation
• /reset — Wipe all your data

**X1 Ecosystem:**
• /xnt — Current XNT price
• /validators — X1 validator info (coming)
• /stake — Staking calculator (coming)

**Models:**
• /model — Show current model
• /model sonnet — Fast, balanced
• /model opus — Best for complex tasks
• /model haiku — Fastest, cheapest

**In groups:**
Mention @echohound_bot or reply to my messages.
"""

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /memory command."""
    user_id = get_user_id(update)
    user_data = user_manager.get_user_context(user_id)

    if not user_data.get("context") and not user_data.get("preferences"):
        await update.message.reply_text("📝 No memories yet. Let's build some!")
        return

    memory_text = "🧠 **What I remember about you:**\n\n"

    if user_data.get("context"):
        memory_text += "**Context:**\n"
        for key, value in user_data["context"].items():
            memory_text += f"• {key}: {value}\n"
        memory_text += "\n"

    if user_data.get("preferences"):
        memory_text += "**Preferences:**\n"
        for key, value in user_data["preferences"].items():
            memory_text += f"• {key}: {value}\n"
        memory_text += "\n"

    memory_text += f"**Sessions:** {len(user_data.get('sessions', []))}\n"
    memory_text += f"**Total messages:** {user_data.get('message_count', 0)}\n"

    await update.message.reply_text(memory_text, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    user_id = get_user_id(update)
    session_id = get_session_id(update)

    # Mark session as cleared
    user_manager.add_context(user_id, f"cleared_session_{session_id}", datetime.now().isoformat())

    await update.message.reply_text("🧹 Conversation cleared. Starting fresh!")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command — wipes all user data."""
    user_id = get_user_id(update)

    keyboard = [
        [InlineKeyboardButton("✅ Yes, delete everything", callback_data=f"reset_confirm:{user_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="reset_cancel")],
    ]

    await update.message.reply_text(
        "⚠️ **This will delete ALL your data.**\n\nAre you sure?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    user_id = get_user_id(update)
    status = rate_limiter.get_status(user_id)

    tier = status["tier"]
    limits = status["limits"]
    usage = status["usage"]

    status_text = f"""📊 **Your Rate Limit Status**

**Tier:** {tier.upper()}
**Total requests:** {status['total_requests']}

**Limits:**
• Per minute: {limits['per_minute']}
• Per hour: {limits['per_hour']}
• Per day: {limits['per_day']}

**Usage:**
• Last minute: {usage['last_minute']}/{limits['per_minute']}
• Last hour: {usage['last_hour']}/{limits['per_hour']}
• Last day: {usage['last_day']}/{limits['per_day']}

{get_tier_hint(tier)}
"""

    await update.message.reply_text(status_text, parse_mode="Markdown")


def get_tier_hint(tier: str) -> str:
    """Get a hint about how to advance tiers."""
    hints = {
        "new": "💡 Stay active for 3+ days and send 50+ messages to advance to ACTIVE tier.",
        "active": "💡 Stay active for 7+ days and send 200+ messages to advance to TRUSTED tier.",
        "trusted": "🌟 You're a trusted user! Enjoy higher limits.",
        "premium": "👑 Premium user — maximum limits.",
    }
    return hints.get(tier, "")


async def xnt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /xnt command."""
    await update.message.reply_text("⏳ Fetching XNT price...")

    try:
        price_info = get_xnt_price()
        await update.message.reply_text(price_info)
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching price: {str(e)}")


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /model command."""
    user_id = get_user_id(update)

    # Get current model
    current = user_manager.get_preference(user_id, "model", DEFAULT_MODEL)

    if context.args:
        # Set new model
        model_key = context.args[0].lower()
        if model_key in MODELS:
            new_model = MODELS[model_key]
            user_manager.set_preference(user_id, "model", new_model)
            await update.message.reply_text(f"✅ Model switched to **{model_key.upper()}**\n\n`{new_model}`", parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"❌ Unknown model: {model_key}\n\nAvailable: sonnet, opus, haiku"
            )
    else:
        # Show current model and options
        keyboard = [
            [InlineKeyboardButton("Sonnet (Balanced)", callback_data="model:sonnet")],
            [InlineKeyboardButton("Opus (Powerful)", callback_data="model:opus")],
            [InlineKeyboardButton("Haiku (Fast)", callback_data="model:haiku")],
        ]

        await update.message.reply_text(
            f"🤖 **Current model:** `{current}`\n\nSelect a model:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = get_user_id(update)

    if data.startswith("model:"):
        model_key = data.split(":")[1]
        if model_key in MODELS:
            new_model = MODELS[model_key]
            user_manager.set_preference(user_id, "model", new_model)
            await query.edit_message_text(
                f"✅ Model switched to **{model_key.upper()}**\n\n`{new_model}`",
                parse_mode="Markdown",
            )

    elif data.startswith("reset_confirm:"):
        confirm_user_id = data.split(":")[1]
        if confirm_user_id == user_id:
            user_manager.clear_user(user_id)
            await query.edit_message_text("💥 All your data has been wiped. Starting fresh!")
        else:
            await query.edit_message_text("❌ User ID mismatch. Reset cancelled.")

    elif data == "reset_cancel":
        await query.edit_message_text("✅ Reset cancelled. Your data is safe.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages with Claude integration."""
    user_id = get_user_id(update)
    session_id = get_session_id(update)

    # Check rate limits
    allowed, error_msg = rate_limiter.check_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"⏳ {error_msg}")
        return

    # Update user activity
    user_manager.update_activity(user_id)
    user_manager.add_session(user_id, session_id)

    # Get user message
    user_message = update.message.text

    # Check if in group and not mentioned
    if update.effective_chat.type in ["group", "supergroup"]:
        bot_username = context.bot.username
        if f"@{bot_username}" not in user_message and not update.message.reply_to_message:
            return  # Ignore group messages that don't mention us

        # Remove mention from message
        user_message = user_message.replace(f"@{bot_username}", "").strip()

    # Get session memory
    session = SessionMemory(session_id)
    session.increment_message()

    # Update current state
    session.update_current_state(f"User said: {user_message[:200]}")
    session.log_work(f"User: {user_message[:100]}")

    # Get user preferences
    model = user_manager.get_preference(user_id, "model", DEFAULT_MODEL)
    user_context = user_manager.get_user_context(user_id)

    # Build system prompt
    system_prompt = build_system_prompt(user_context, session)

    try:
        # Call Claude
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        # Extract response text
        response_text = response.content[0].text

        # Save to session
        session.log_work(f"Assistant: {response_text[:100]}")

        # Check for memory tags in response
        memories = session.extract_memories()
        for mem in memories:
            memory_manager.save_memory(mem)
            user_manager.add_context(user_id, f"memory_{mem.type}", mem.content[:100])

        # Send response
        await update.message.reply_text(response_text)

    except Exception as e:
        logger.error(f"Error calling Claude: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


def build_system_prompt(user_context: dict, session: SessionMemory) -> str:
    """Build the system prompt with memory injection."""
    prompt = """You are EchoHound 🐾 — a sharp, direct, community-first AI assistant.

**Guidelines:**
- Be concise but thorough
- Use tools when helpful (web search, file operations, shell commands)
- Remember: you're built for Telegram communities

**Current Session:**
"""

    # Add session context
    prompt += session.get_session_summary()
    prompt += "\n\n"

    # Add user context if available
    if user_context.get("context"):
        prompt += "**About this user:**\n"
        for key, value in user_context["context"].items():
            if not key.startswith("memory_"):
                prompt += f"- {key}: {value}\n"
        prompt += "\n"

    if user_context.get("preferences"):
        prompt += "**User preferences:**\n"
        for key, value in user_context["preferences"].items():
            prompt += f"- {key}: {value}\n"
        prompt += "\n"

    prompt += """**Memory tagging:**
You can tag memories for long-term storage using:
[SAVE_MEMORY type=user|feedback|project|reference]content[/SAVE_MEMORY]

Types:
- user: Facts about the user (expertise, preferences)
- feedback: Corrections or confirmations
- project: Ongoing work or decisions
- reference: External systems/docs
"""

    return prompt


def main():
    """Run the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable required")
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY environment variable required")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("memory", memory_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("xnt", xnt_command))
    application.add_handler(CommandHandler("model", model_command))

    # Callback handler for inline buttons
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Message handler (must be last)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🐾 EchoHound v2 starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
