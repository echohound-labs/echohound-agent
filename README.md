# 🐾 EchoHound v2

Sharp, direct, community-first AI agent — powered by Claude. Built for Telegram communities.


---

## What EchoHound Does

| Feature | Status | Details |
|---|---|---|
| 🔍 Web search | ✅ | Brave Search API + DuckDuckGo fallback |
| 🌐 Web fetch | ✅ | Full page extraction, clean text output |
| 📁 File operations | ✅ | Sandboxed read/write/list/delete |
| 💻 Shell commands | ✅ | Safety-limited, confirmation-gated |
| 💰 X1 price tool | ✅ | XNT price, any token, holders, gas stats |
| 🧠 KAIROS session memory | ✅ | 9-section template, background extraction |
| 📝 Typed long-term memory | ✅ | user / feedback / project / reference |
| 👥 Community memory | ✅ | Shared knowledge across all users |
| 💭 Dream pass | ✅ | Memory extraction every 5 messages |
| 🌙 AutoDream | ✅ | Nightly consolidation (24h + 5 sessions) |
| 📦 AutoCompact | ✅ | Context window management at 87% |
| 🤖 Swarm | ✅ | Parallel subagent coordination |
| ✅ TodoWrite | ✅ | Task tracking + verification nudge |
| ⏱️ Rate limiter | ✅ | Tier-based (admin/whitelist/normal/new_user) |
| 💬 Telegram bot | ✅ | Mention-aware, /x command prefix |

---

## Project Structure

```
echohound-agent/
├── agent.py                 ← v1 agent (kept for reference)
├── agent_v2.py              ← v2 agent — all KAIROS components wired
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
├── services/                ← new in v2
│   ├── auto_dream.py        ← nightly consolidation (4-phase)
│   ├── auto_compact.py      ← context window management
│   ├── swarm.py             ← parallel subagent coordinator
│   └── todo.py              ← TodoWrite with verification nudge
│
└── utils/
    └── rate_limiter.py      ← tier-based rate limiting
```

---

## Quick Start

### 1. Clone and install
```bash
git clone https://github.com/echohound-labs/echohound-agent.git
cd echohound-agent
pip install -r requirements.txt
```

### 2. Set up API keys
```bash
cp .env.example .env
# Edit .env and fill in your keys
```

Required:
- `ANTHROPIC_API_KEY` → https://console.anthropic.com
- `TELEGRAM_BOT_TOKEN` → get from @BotFather

Optional:
- `BRAVE_API_KEY` → https://api.search.brave.com (free tier available)

### 3. Run
```bash
python telegram_bot_v2.py
```

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

**Key insight**: EchoHound saves feedback on BOTH corrections ("stop doing X") AND confirmations ("yes exactly, keep that"). Most bots only save corrections. Saving confirmations is what keeps it consistent across sessions.

### Community Memory (`memory/user_manager.py`)
Separate from per-user memory — facts relevant to the whole group are saved to `memory/community.md` and injected for all users.

### Dream Pass
Every 5 messages, a background subagent reads the recent conversation and extracts typed memories. Cheap, non-blocking, automatic.

### AutoDream (`services/auto_dream.py`)
Fires after 24h + 5 sessions accumulated. 4-phase pipeline:
1. **Orient** — read existing consolidated memory
2. **Gather** — extract signal from session files
3. **Consolidate** — merge, fix contradictions, keep newer on conflict
4. **Prune** — keep index entries under 150 chars

### AutoCompact (`services/auto_compact.py`)
Fires at ~87% context window usage. Leaves 13K token buffer. Circuit-breaks after 3 consecutive failures to stop wasting API calls.

### Swarm (`services/swarm.py`)
Spawn parallel subagents for independent tasks. Workers share parent context and report back to the coordinator.

### TodoWrite (`services/todo.py`)
The todo list is a real tool with state. Verification nudge: complete 3+ tasks without a verification step and it reminds you to check your work before finishing.

---

## Bot Commands

All commands use `/x` prefix to avoid collisions with other bots.

| Command | What it does |
|---|---|
| `/start` | Introduction |
| `/xhelp` | Show all commands |
| `/xmemory` | View EchoHound's memory of you |
| `/xdream` | Show dream pass summary |
| `/xstatus` | Agent health (compact, dream, memory) |
| `/xclear` | Clear conversation history (keeps memory) |
| `/xreset` | Wipe all your memory entirely |
| `/xrate` | Check your rate limit status |

In groups, mention `@yourbotname` or reply to a bot message to trigger a response.

---

## Rate Limiting

Four tiers:

| Tier | Limit | Notes |
|---|---|---|
| `admin` | Unlimited | User IDs in `ADMIN_USER_IDS` in config.py |
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
Build system prompt:
  personality + KAIROS session state + typed memories + community memory
     ↓
Call Claude API with all tools attached
     ↓
Claude decides: answer directly OR use tool(s)
     ↓  (if tool)
Permission check → execute → feed result back → loop
     ↓
Final response → send to user
     ↓
Background: session memory extraction (if thresholds met)
Background: dream pass (every 5 messages)
```

---

## Deploy on a VPS

```ini
# /etc/systemd/system/echohound.service
[Unit]
Description=EchoHound v2
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
```

---

## Extending EchoHound

### Add a new tool
1. Create `tools/my_tool.py`
2. Add to `TOOL_MAP` and `CORE_TOOL_DEFINITIONS` in `agent_v2.py`
3. Claude uses it automatically

### Add a memory type
1. Add to `MEMORY_TYPES` in `memory/session_memory.py`
2. Update `memory_save` tool description in `agent_v2.py`

---

## Changelog

### v2.0 — March 31, 2026
- ✨ KAIROS session memory fully wired into agent loop (was built but unused in v1)
- ✨ 4-type typed memory (user / feedback / project / reference)
- ✨ Community memory — shared group knowledge separate from per-user memory
- ✨ Dream pass every 5 messages
- ✨ AutoDream nightly consolidation (4-phase)
- ✨ AutoCompact context window management with circuit breaker
- ✨ Swarm parallel subagents
- ✨ TodoWrite with verification nudge
- ✨ Tier-based rate limiter
- ✨ `/x` command prefix, `/xdream` `/xstatus` `/xrate` commands
- ✨ `services/` layer connecting everything

### v1.0 — March 2026
- Initial release: web search, fetch, file ops, shell, X1 price tool, basic memory

---

## Credits

Built by Skywalker with help from Theo (Claude Sonnet 4.6 via OpenClaw).
Architecture patterns from the Claude Code source leak — March 31, 2026.

## License

MIT — use it, extend it, make it yours.
