# 🐾 EchoHound v2

Sharp, direct, community-first AI agent — powered by Claude. Built for Telegram communities.


---

## What EchoHound Does

| Feature | Details |
|---|---|
| 🔍 Web search | Brave Search API + DuckDuckGo fallback |
| 🌐 Web fetch | Full page extraction, clean text output |
| 📁 File operations | Sandboxed read/write/list/delete |
| 💻 Shell commands | Safety-limited, confirmation-gated |
| 💰 X1 price tool | XNT price, any token, holders, gas stats |
| 🧠 KAIROS session memory | 9-section template, background extraction |
| 📝 Typed long-term memory | user / feedback / project / reference |
| 👥 Community memory | Shared knowledge across all users |
| 💭 Dream pass | Memory extraction every 5 messages |
| 🌙 AutoDream | Nightly consolidation (24h + 5 sessions) |
| 📦 AutoCompact | Context window management at 87% |
| 🤖 Swarm | Parallel subagent coordination |
| ✅ TodoWrite | Task tracking + verification nudge |
| ⏱️ Rate limiter | Tier-based (admin/whitelist/normal/new_user) |
| 🔁 API retry | Exponential backoff + jitter on 429/529 errors |
| 💸 Cost tracking | USD cost + token breakdown per session |
| 🎭 Spinner verbs | 187 personality verbs while thinking |
| 💬 Telegram bot | Mention-aware, /x command prefix |

---

## Project Structure

```
echohound-agent/
├── agent.py                 ← v1 agent (kept for reference)
├── agent_v2.py              ← v2 agent — everything wired together
├── telegram_bot.py          ← v1 bot (kept for reference)
├── telegram_bot_v2.py       ← v2 bot — use this
├── config.py                ← all settings in one place
│
├── memory/
│   ├── session_memory.py    ← KAIROS: 9-section template + 4-type taxonomy
│   ├── user_manager.py      ← per-user + community memory
│   └── manager.py           ← v1 flat memory (kept for reference)
│
├── tools/
│   ├── web_search.py        ← Brave Search + DuckDuckGo fallback
│   ├── web_fetch.py         ← URL fetch + HTML to text
│   ├── file_ops.py          ← sandboxed file operations
│   ├── exec_tool.py         ← shell with safety limits
│   └── x1_price.py         ← XNT price, any token, holders, gas
│
├── services/
│   ├── auto_dream.py        ← nightly consolidation (4-phase)
│   ├── auto_compact.py      ← context window management
│   ├── swarm.py             ← parallel subagent coordinator
│   └── todo.py              ← TodoWrite with verification nudge
│
└── utils/
    ├── rate_limiter.py      ← tier-based rate limiting
    ├── api_retry.py         ← exponential backoff + jitter (429/529)
    ├── cost_tracker.py      ← USD cost + token tracking per session
    ├── spinner.py           ← 187 personality verbs + stall animation
    └── token_budget.py      ← natural language token budget parser
```

---

## Installation

### Requirements
- Python 3.10+
- Anthropic API key
- Telegram bot token
- Optional: Brave Search API key

### Step 1 — Clone the repo
```bash
git clone https://github.com/echohound-labs/echohound-agent.git
cd echohound-agent
```

### Step 2 — Install dependencies
```bash
pip install -r requirements.txt
```

On Ubuntu/Debian if you get permission errors:
```bash
pip install -r requirements.txt --break-system-packages
```

### Step 3 — Create your .env file
```bash
cp .env.example .env
nano .env
```

Fill in your keys:
```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456789:ABC...
BRAVE_API_KEY=BSA...          # optional but recommended
```

### Step 4 — Set yourself as admin

Open `config.py` and add your Telegram user ID to `ADMIN_USER_IDS`:
```python
ADMIN_USER_IDS = [
    123456789,  # your Telegram user ID
]
```

To find your Telegram ID, message **@userinfobot** on Telegram.

### Step 5 — Run
```bash
python telegram_bot_v2.py
```

You should see:
```
INFO - 🐾 EchoHound v2 starting...
```

---

## Setting Up Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name: `EchoHound`
4. Choose a username ending in `bot`: e.g. `echohound_bot`
5. Copy the token BotFather gives you into your `.env`

**Adding to a group:**
1. Open your group → tap group name → Add Members
2. Search for your bot's username and add it
3. In groups, EchoHound only responds when `@mentioned` or replied to

---

## Bot Commands

All commands use `/x` prefix to avoid collisions with other bots.

| Command | What it does |
|---|---|
| `/start` | Introduction |
| `/xhelp` | Show all commands |
| `/xmemory` | View EchoHound's memory of you |
| `/xdream` | Show dream pass summary |
| `/xstatus` | Agent health — compact stats, dream passes, cost |
| `/xcost` | Full session cost breakdown (USD + token counts) |
| `/xclear` | Clear conversation history (keeps long-term memory) |
| `/xreset` | Wipe all your memory entirely |
| `/xrate` | Check your rate limit status and tier |

In groups, mention `@yourbotname` or reply to a bot message to trigger a response.

---

## Architecture — KAIROS Memory System

All memory patterns are derived from the Claude Code source leak (March 31, 2026).

### Session Memory (`memory/session_memory.py`)
Every conversation gets a structured 9-section template:

```
# Session Title
# Current State       ← read this first after any gap
# Task Specification
# Files and Functions
# Workflow
# Errors & Corrections
# Learnings
# Key Results
# Worklog
```

Two thresholds must **both** be met before extraction fires: message count AND tool call count. Runs as a background task — never blocks your response.

### Typed Long-Term Memory
Four hard types, each with strict format rules:

| Type | What | Format |
|---|---|---|
| `user` | Who they are, expertise, preferences | Fact + Why it matters |
| `feedback` | Corrections AND confirmations | Rule + Why + Apply |
| `project` | Ongoing work, decisions | Fact + Why + Apply |
| `reference` | External systems, docs | Pointer + purpose |

**Key insight:** EchoHound saves feedback on BOTH corrections ("stop doing X") AND confirmations ("yes exactly, keep that"). Most bots only save corrections. Saving confirmations is what keeps it consistent across sessions.

### Community Memory (`memory/user_manager.py`)
Separate from per-user memory — facts relevant to the whole group are saved to `memory/community.md` and injected for every user.

### Dream Pass
Every 5 messages, a background subagent reads the recent conversation and extracts typed memories. Non-blocking, automatic.

### AutoDream (`services/auto_dream.py`)
Fires after 24h elapsed + 5 sessions accumulated. 4-phase pipeline:
1. **Orient** — read existing consolidated memory
2. **Gather** — extract signal from session files
3. **Consolidate** — merge, fix contradictions, keep newer on conflict
4. **Prune** — keep index entries under 150 chars

### AutoCompact (`services/auto_compact.py`)
Fires at ~87% context window usage. Leaves a 13K token buffer. Circuit-breaks after 3 consecutive failures to stop wasting API calls.

### Swarm (`services/swarm.py`)
Spawn parallel subagents for independent tasks. Workers share parent context and report results back to the coordinator.

### TodoWrite (`services/todo.py`)
The todo list is a real tool with state. Verification nudge: complete 3+ tasks without a verification step and EchoHound reminds you to check your work before finishing.

---

## Reliability

### API Retry (`utils/api_retry.py`)
Without retry logic, Anthropic API 429 (rate limit) and 529 (overloaded) errors crash silently. `api_retry.py` handles this automatically:

- Exponential backoff: 500ms → 1s → 2s → 4s → ... → 32s max
- ±25% jitter to prevent thundering herd
- Respects `retry-after` response headers
- Circuit breaks after 3 consecutive 529 overload errors
- Max 10 retries before giving up and raising the error

### Cost Tracking (`utils/cost_tracker.py`)
Tracks USD cost and token usage per session across every API call. Breaks down input, output, cache read, and cache write tokens with per-model pricing. View with `/xcost` or in the `/xstatus` summary.

### Spinner Verbs (`utils/spinner.py`)
187 personality verbs shown while EchoHound is thinking:
```
Cerebrating... Boondoggling... Reticulating... Burrowing...
```
After 8 seconds, switches to a stalled message so the user knows it's still working:
```
Still here. Just really into this problem 🐾
```

---

## Rate Limiting

| Tier | Limit | Notes |
|---|---|---|
| `admin` | Unlimited | User IDs in `ADMIN_USER_IDS` in `config.py` |
| `whitelisted` | Unlimited | Set per user |
| `normal` | 10/min, 50/hr | Default for established users |
| `new_user` | 5/min, 20/hr | First 24 hours |

Progressive cooldowns on violations: 1min → 5min → 15min → 30min → 60min.

---

## Agentic Loop v2

```
User message
     ↓
Rate limiter: check tier + allowance
     ↓
Token budget parser: extract "+500k" style directives if present
     ↓
Build system prompt:
  personality + KAIROS session state + typed memories + community memory
     ↓
Call Claude API — with retry/backoff on 429/529
Track cost + tokens after each call
     ↓
Claude decides: answer directly OR use tool(s)
     ↓  (if tool)
Permission check → execute → feed result back → loop
     ↓
Final response → strip [SAVE_MEMORY] tags → send to user
If thinking > 8s → stall message sent while waiting
     ↓
Background: session memory extraction (if thresholds met)
Background: dream pass (every 5 messages)
```

---

## Deploy on a VPS (24/7)

### systemd (recommended)

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

```bash
sudo systemctl daemon-reload
sudo systemctl enable echohound
sudo systemctl start echohound
sudo systemctl status echohound
```

### Quick option (screen)
```bash
screen -S echohound
python telegram_bot_v2.py
# Ctrl+A then D to detach
# screen -r echohound to reattach
```

---

## Extending EchoHound

### Add a new tool
1. Create `tools/my_tool.py` with your function
2. Add to `TOOL_MAP` and `CORE_TOOL_DEFINITIONS` in `agent_v2.py`
3. Claude picks it up automatically

### Add a memory type
1. Add to `MEMORY_TYPES` in `memory/session_memory.py`
2. Update the `memory_save` tool description in `agent_v2.py`

### Change the model
Edit `config.py`:
```python
MODEL = "claude-haiku-3-5"    # cheapest, fast
MODEL = "claude-sonnet-4-5"   # default, best balance
MODEL = "claude-opus-4-5"     # most capable, most expensive
```

---

## Changelog

### v2.1 — April 2026
- ✨ API retry with exponential backoff + jitter (`utils/api_retry.py`)
- ✨ Session cost tracking in USD + full token breakdown (`utils/cost_tracker.py`)
- ✨ 187 spinner personality verbs + stall animation after 8s (`utils/spinner.py`)
- ✨ Natural language token budget parser (`utils/token_budget.py`)
- ✨ `/xcost` command — view session cost in Telegram
- ✨ Cost summary added to `/xstatus`
- 🔧 `.gitignore` updated to exclude session/user memory files

### v2.0 — March 31, 2026
- ✨ KAIROS session memory fully wired into agent loop
- ✨ 4-type typed memory (user / feedback / project / reference)
- ✨ Community memory — shared group knowledge
- ✨ Dream pass every 5 messages
- ✨ AutoDream nightly consolidation (4-phase)
- ✨ AutoCompact context window management with circuit breaker
- ✨ Swarm parallel subagents
- ✨ TodoWrite with verification nudge
- ✨ Tier-based rate limiter
- ✨ `/x` command prefix + `/xdream` `/xstatus` `/xrate`
- ✨ `services/` layer connecting everything

### v1.0 — March 2026
- Initial release: web search, fetch, file ops, shell, X1 price tool, basic memory

---

## Credits

Built by Skywalker with help from Theo (Claude Sonnet 4.6 via OpenClaw).

## License

MIT — use it, extend it, make it yours.
