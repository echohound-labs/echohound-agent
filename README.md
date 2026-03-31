# 🐾 EchoHound v2

> Sharp, direct, community-first AI agent — powered by Claude.
> Built for Telegram communities. Inspired by the Claude Code architecture leak.

---

## What EchoHound Does v2

| Feature | Status |
|---------|--------|
| 🔍 **Web search** | Brave Search API + DuckDuckGo fallback |
| 🌐 **Web fetch** | Full page extraction with markdown |
| 📁 **File operations** | Sandboxed read/write/list |
| 💻 **Shell commands** | Safety-limited execution |
| 🧠 **Typed memory** | Session notes, observations, preferences, bookmarks |
| 💭 **Dream pass** | Auto-generated summaries every 5 messages |
| 👤 **User manager** | Per-user context tracking |
| ⏱️ **Rate limiter** | Per-user rate limiting |
| 💰 **X1 price tool** | Native X1 blockchain token prices |
| 💬 **Telegram bot** | Mention-aware group responses |

---

## Project Structure v2

```
echohound/
├── agent_v2.py              ← Core agent with typed memory + dream pass
├── telegram_bot_v2.py       ← Telegram bot with user manager + rate limiter
├── config.py                ← Centralized config
├── tools/
│   ├── __init__.py          ← Tool registry
│   ├── web_search.py        ← Brave Search + DDG fallback
│   ├── web_fetch.py         ← URL fetch + HTML→markdown
│   ├── file_ops.py          ← Sandboxed file ops
│   ├── exec_tool.py         ← Shell with safety limits
│   └── x1_price.py          ← X1 blockchain price queries
├── memory/
│   ├── memory.md            ← Typed memory store
│   ├── manager.py           ← Memory read/write/trim
│   └── types.py             ← Note/Observation/Preference/Bookmark
├── utils/
│   ├── user_manager.py      ← Per-user session tracking
│   └── rate_limiter.py      ← Rate limiting
├── telegram_bot.py          ← Legacy v1 bot (kept for reference)
└── agent.py                 ← Legacy v1 agent (kept for reference)
```

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/echohound-labs/echohound-agent.git
cd echohound-agent
pip install -r requirements.txt
```

### 2. Set up your API keys

```bash
cp .env.example .env
# Edit .env and fill in your keys
```

Required:
- **Anthropic API key** → https://console.anthropic.com
- **Telegram bot token** → get from @BotFather
- **Brave Search API key** → https://api.search.brave.com (optional)

Optional:
- **X1 RPC endpoint** → for native X1 price queries (defaults to public RPC)

### 3. Run v2 Telegram bot

```bash
python telegram_bot_v2.py
```

---

## v2 Architecture

### Typed Memory System

Every memory is typed:

```python
class Note:          # Factual information
class Observation:   # Things noticed about users
class Preference:    # User preferences
class Bookmark:      # Saved URLs/topics
```

Auto-generated tags + relevance scoring.

### Dream Pass

Every 5 messages, EchoHound generates a running summary:

```
Dream Summary #3 | 2026-03-31 10:45 UTC
├── Context: X1 ecosystem tools, price monitoring
├── Active threads: validator staking, grant applications
├── Pending: Token economics discussion
└── Mood: Technical, focused, collaborative
```

### User Manager

Per-user tracking:
- User ID, username, first interaction
- Message count, memory references
- Current session context
- Rate limit status

### Rate Limiter

- Default: 30 messages/minute per user
- Burst: 10 messages allowed
- Auto-reset after window expires

### X1 Price Tool

Native X1 blockchain integration:
- Query any X1 token price
- Uses XDEX API + on-chain data
- No API key required

---

## Bot Commands

| Command | What it does |
|---------|-------------|
| `/start` | Introduction + user registration |
| `/help` | Show v2 feature list |
| `/memory` | View your memories |
| `/dream` | Show last dream summary |
| `/clear` | Clear your session |
| `/reset` | Wipe all your data |
| `/rate` | Check your rate limit status |

---

## Deploying on a VPS

### systemd service (recommended)

Create `/etc/systemd/system/echohound.service`:

```ini
[Unit]
Description=EchoHound v2 Telegram Bot
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/path/to/echohound-agent
ExecStart=/usr/bin/python3 telegram_bot_v2.py
EnvironmentFile=/path/to/echohound-agent/.env
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
```

---

## The Agentic Loop v2

```
User message
     ↓
User manager: identify + track
     ↓
Rate limiter: check allowance
     ↓
Build prompt (personality + typed memories + dream pass)
     ↓
Call Claude API with v2 tools
     ↓
Claude decides: direct answer OR tool use
     ↓  (if tool)
Execute tool → feed result → loop
     ↓
Final response → send
     ↓
Memory manager: extract + save typed memories
     ↓
Dream pass: update if message count threshold
```

---

## Extending EchoHound v2

### Add a new tool

1. Create `tools/my_tool.py` with your function
2. Add to `TOOL_DEFINITIONS` and `TOOL_MAP` in `tools/__init__.py`
3. Claude will use it automatically

### Add a memory type

1. Add class to `memory/types.py`
2. Update `MemoryManager.save()` in `memory/manager.py`
3. Add extraction prompt in `agent_v2.py`

---

## Changelog

### v2.0 — March 31, 2026
- ✨ Typed memory system (notes, observations, preferences, bookmarks)
- ✨ Dream pass (auto-summaries every 5 messages)
- ✨ User manager (per-user tracking)
- ✨ Rate limiter (30/min default)
- ✨ X1 price tool (native blockchain queries)
- ✨ v2 bot with full feature parity

### v1.0 — March 2026
- Initial release
- Web search, fetch, file ops, shell commands
- Basic memory (flat file)

---

## Credits

Built by **Skywalker** with help from **Theo** (Claude Sonnet 4.6 via OpenClaw).

Architecture patterns inspired by the Claude Code source leak — March 31, 2026.

---

## License

MIT — use it, extend it, make it yours.
