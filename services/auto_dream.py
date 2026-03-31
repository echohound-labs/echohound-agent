"""
AutoDream — Nightly Memory Consolidation
Fires after 24h elapsed + 5 new sessions accumulated.
4-phase pipeline: Orient → Gather → Consolidate → Prune
"""
import asyncio
import glob
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from config import ANTHROPIC_API_KEY, MODEL, SESSIONS_DIR

MIN_HOURS    = 24
MIN_SESSIONS = 5
MAX_ENTRY    = 150
DREAM_LOG    = SESSIONS_DIR / "dream_log.json"


class AutoDream:
    def __init__(self, client=None):
        import anthropic
        self.client = client or anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def _load_log(self) -> dict:
        return json.loads(DREAM_LOG.read_text()) if DREAM_LOG.exists() else {"last_dream": None, "runs": 0}

    def _save_log(self, log: dict):
        DREAM_LOG.parent.mkdir(parents=True, exist_ok=True)
        DREAM_LOG.write_text(json.dumps(log, indent=2))

    def _new_sessions(self, since: Optional[str]) -> list:
        files = glob.glob(str(SESSIONS_DIR / "*_session.md"))
        if not since:
            return files
        cutoff = datetime.fromisoformat(since)
        return [f for f in files if datetime.fromtimestamp(os.path.getmtime(f)) > cutoff]

    def should_dream(self) -> tuple[bool, str]:
        log  = self._load_log()
        last = log.get("last_dream")
        if last:
            elapsed = datetime.utcnow() - datetime.fromisoformat(last)
            if elapsed < timedelta(hours=MIN_HOURS):
                return False, f"Next dream in {timedelta(hours=MIN_HOURS) - elapsed}"
        new = self._new_sessions(last)
        if len(new) < MIN_SESSIONS:
            return False, f"{len(new)}/{MIN_SESSIONS} sessions accumulated"
        return True, f"{len(new)} sessions ready"

    async def run(self) -> dict:
        eligible, reason = self.should_dream()
        if not eligible:
            return {"status": "skipped", "reason": reason}

        log      = self._load_log()
        sessions = self._new_sessions(log.get("last_dream"))
        print(f"[AutoDream] Starting — {reason}")

        try:
            existing = self._orient()
            signal   = await self._gather(sessions)
            merged   = await self._consolidate(existing, signal)
            pruned   = self._prune(merged)

            out = SESSIONS_DIR / "consolidated_memory.md"
            out.write_text(pruned)

            log["last_dream"] = datetime.utcnow().isoformat()
            log["runs"]       = log.get("runs", 0) + 1
            self._save_log(log)
            print(f"[AutoDream] ✅ Done — {len(sessions)} sessions")
            return {"status": "completed", "sessions": len(sessions)}
        except Exception as e:
            print(f"[AutoDream] ❌ {e}")
            return {"status": "failed", "error": str(e)}

    def _orient(self) -> str:
        p = SESSIONS_DIR / "consolidated_memory.md"
        return p.read_text() if p.exists() else "(no existing memory)"

    async def _gather(self, paths: list) -> str:
        parts = []
        for p in paths[:20]:
            try:
                parts.append(f"--- {Path(p).name} ---\n{Path(p).read_text()[:400]}")
            except Exception:
                pass
        resp = await asyncio.to_thread(
            self.client.messages.create,
            model=MODEL, max_tokens=600,
            messages=[{"role": "user", "content":
                f"Extract facts worth remembering long-term from these sessions.\n"
                f"Include confirmations, not just corrections.\n"
                f"Output a clean bulleted list, each under {MAX_ENTRY} chars.\n\n"
                + "\n\n".join(parts)[:5000]
            }],
        )
        return resp.content[0].text

    async def _consolidate(self, existing: str, signal: str) -> str:
        resp = await asyncio.to_thread(
            self.client.messages.create,
            model=MODEL, max_tokens=1200,
            messages=[{"role": "user", "content":
                f"Merge new signal into existing memory. Fix contradictions (keep newer).\n"
                f"Sections: USER, FEEDBACK (corrections), FEEDBACK (confirmations), PROJECT, REFERENCE.\n"
                f"Each entry under {MAX_ENTRY} chars. Output clean markdown only.\n\n"
                f"EXISTING:\n{existing[:3000]}\n\nNEW:\n{signal[:2000]}"
            }],
        )
        return resp.content[0].text

    def _prune(self, text: str) -> str:
        lines = []
        for line in text.split("\n"):
            if line.strip().startswith("-") and len(line.strip()) > MAX_ENTRY:
                line = line[:MAX_ENTRY] + "…"
            lines.append(line)
        return "\n".join(lines)


async def run_dream_scheduler(dream: AutoDream, interval: int = 3600):
    """Start as background task at bot startup."""
    print("[AutoDream] Scheduler started")
    while True:
        try:
            await dream.run()
        except Exception as e:
            print(f"[AutoDream] Scheduler error: {e}")
        await asyncio.sleep(interval)
