# 🐾 EchoHound

> Sharp, direct, community-first AI agent — powered by Claude.  
> Built for Telegram communities.

---

## What EchoHound Does

- 🔍 **Web search** — finds current information via Brave Search API
- 🌐 **Web fetch** — reads full pages and extracts clean text
- 📁 **File operations** — read, write, list files (sandboxed)
- 💻 **Shell commands** — runs commands with safety limits
- 🧠 **Memory** — remembers things across conversations (KAIROS-style)
- 💬 **Telegram bot** — your community talks to it just like a person

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/echohound
cd echohound
pip install -r requirements.txt
```

### 2. Set up your API keys

```bash
cp .env.example .env
# Edit .env and fill in your keys
```

You need:
- **Anthropic API key** → https://console.anthropic.com
- **Telegram bot token** → get from @BotFather (instructions below)
- **Brave Search API key** → https://api.search.brave.com (optional, free tier available)

### 3. Run in CLI mode (test it first)

```bash
python agent.py
```

### 4. Run as Telegram bot

```bash
python telegram_bot.py
```

---

## Setting Up Your Telegram Bot

### Step 1 — Create the bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name: `EchoHound` (or whatever you want)
4. Choose a username: `echohound_bot` (must end in `bot`)
5. BotFather gives you a token — copy it

### Step 2 — Configure the token

Add to your `.env`:
```
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
```

### Step 3 — Add to your group

1. Open your Telegram group
2. Click group name → Add Members
3. Search for `@echohound_bot` (your bot's username)
4. Add it

### Step 4 — In groups, mention the bot

EchoHound only responds in groups when:
- You mention it: `@echohound_bot what's the BTC price?`
- Or you reply to one of its messages

In DMs it responds to everything.

---

## Bot Commands

| Command | What it does |
|---------|-------------|
| `/start` | Introduction message |
| `/help` | Show help |
| `/memory` | View EchoHound's memory |
| `/clear` | Clear your conversation history |
| `/reset` | Wipe memory entirely (use carefully) |

---

## Deploying on a VPS (so it runs 24/7)

### Option A — Simple (screen)

```bash
screen -S echohound
python telegram_bot.py
# Ctrl+A, D to detach
```

### Option B — systemd service (recommended)

Create `/etc/systemd/system/echohound.service`:
```ini
[Unit]
Description=EchoHound Telegram Bot
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/path/to/echohound
ExecStart=/usr/bin/python3 telegram_bot.py
EnvironmentFile=/path/to/echohound/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable echohound
sudo systemctl start echohound
sudo systemctl status echohound
```

### Option C — Railway / Render (easiest for beginners)

1. Push this repo to GitHub
2. Go to https://railway.app or https://render.com
3. Connect your GitHub repo
4. Add environment variables in their dashboard
5. Deploy — they handle the rest

---

## Architecture

Inspired by patterns found in the Claude Code source leak:

```
echohound/
├── agent.py           ← Core agentic loop (tool use, memory, permissions)
├── telegram_bot.py    ← Telegram interface
├── config.py          ← All settings in one place
├── tools/
│   ├── web_search.py  ← Brave Search API + DuckDuckGo fallback
│   ├── web_fetch.py   ← URL fetcher + HTML extractor
│   ├── file_ops.py    ← Sandboxed file read/write/list
│   └── exec_tool.py   ← Shell commands with safety limits
└── memory/
    ├── memory.md      ← Flat file memory store
    └── manager.py     ← KAIROS-style read/write/trim logic
```

### The Agentic Loop (how it thinks)

```
User message
     ↓
Build system prompt (personality + injected memory)
     ↓
Call Claude API with tools attached
     ↓
Claude decides: answer directly OR use a tool
     ↓  (if tool use)
Permission check → execute tool → feed result back to Claude
     ↓  (loop until no more tool calls)
Final response → send to user
     ↓
Maybe save something to memory
```

---

## Extending EchoHound

### Add a new tool

1. Create `tools/my_tool.py` with a function
2. Add it to `TOOL_DEFINITIONS` in `tools/__init__.py`
3. Add it to `TOOL_MAP` in `tools/__init__.py`
4. That's it — Claude will start using it automatically

### Phase 2 — Coming features
- Sub-agent coordinator (spawn parallel workers)
- Blockchain/oracle integration
- Trading/price monitoring
- Voice mode

---

## Credits

Built by Skywalker with help from Theo (Claude Sonnet 4.6 via OpenClaw).  
Architecture patterns inspired by the Claude Code source leak — March 31, 2026.

---

## License

MIT — use it, extend it, make it yours.
