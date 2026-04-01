"""
EchoHound Swarm — Parallel sub-agents with tool access
FIX: Workers now have web_search + web_fetch + read_file tools
"""

import asyncio
import logging
from pathlib import Path
import anthropic
from config import ANTHROPIC_API_KEY, MODEL

logger = logging.getLogger("echohound.swarm")

WORKER_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch and read the content of a URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a local text file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]


async def _execute_tool(tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "web_search":
            return await _tool_web_search(tool_input["query"], tool_input.get("num_results", 5))
        elif tool_name == "web_fetch":
            return await _tool_web_fetch(tool_input["url"])
        elif tool_name == "read_file":
            return await _tool_read_file(tool_input["path"])
        return f"[Unknown tool: {tool_name}]"
    except Exception as e:
        return f"[Tool error: {tool_name} — {e}]"


async def _tool_web_search(query: str, num_results: int = 5) -> str:
    try:
        import httpx
        from config import BRAVE_API_KEY
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
                params={"q": query, "count": num_results},
            )
            r.raise_for_status()
            results = r.json().get("web", {}).get("results", [])
            lines = [f"{i}. {res.get('title','')}\n {res.get('url','')}\n {res.get('description','')}"
                     for i, res in enumerate(results[:num_results], 1)]
            return "\n\n".join(lines) if lines else "[No results found]"
    except Exception:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1})
                data = r.json()
                if data.get("AbstractText"):
                    return data["AbstractText"]
                topics = [t.get("Text", "") for t in data.get("RelatedTopics", [])[:5]
                          if isinstance(t, dict) and t.get("Text")]
                return "\n".join(topics) if topics else f"[No results for: {query}]"
        except Exception as e2:
            return f"[Search failed: {e2}]"


async def _tool_web_fetch(url: str) -> str:
    try:
        import httpx
        from html.parser import HTMLParser

        class _Strip(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
            def handle_data(self, data):
                if data.strip():
                    self.parts.append(data.strip())
            def get_text(self):
                return "\n".join(self.parts)

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "EchoHound/2.0"})
            r.raise_for_status()
            parser = _Strip()
            parser.feed(r.text)
            text = parser.get_text()
            return text[:8000] + "\n[...truncated]" if len(text) > 8000 else text or "[No readable text]"
    except Exception as e:
        return f"[Fetch failed: {e}]"


async def _tool_read_file(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"[File not found: {path}]"
        if p.stat().st_size > 100_000:
            return f"[File too large: {p.stat().st_size:,} bytes]"
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[File read error: {e}]"


class SwarmCoordinator:
    def __init__(self, client=None, max_concurrent: int = 4, model: str = None):
        self.model = model or MODEL
        self.client = client or anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._sem = asyncio.Semaphore(max_concurrent)

    async def run(self, tasks: list[dict], system: str = "") -> list[dict]:
        results = await asyncio.gather(
            *[self._run_task(t, system) for t in tasks],
            return_exceptions=True,
        )
        output = []
        for i, (task, result) in enumerate(zip(tasks, results)):
            if isinstance(result, Exception):
                output.append({"task": task.get("name", f"task_{i}"), "result": f"Error: {result}", "success": False})
            else:
                output.append({"task": task.get("name", f"task_{i}"), "result": result, "success": True})
        return output

    async def _run_task(self, task: dict, system: str = "") -> str:
        async with self._sem:
            messages = [{"role": "user", "content": task.get("prompt", str(task))}]

            for _ in range(5):
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=2048,
                    system=system or "You are a focused research sub-agent. Complete the task thoroughly using available tools.",
                    tools=WORKER_TOOLS,
                    messages=messages,
                )

                text_parts, tool_calls = [], []
                for block in response.content:
                    if block.type == "text": text_parts.append(block.text)
                    elif block.type == "tool_use": tool_calls.append(block)

                messages.append({"role": "assistant", "content": response.content})

                if not tool_calls:
                    return "\n".join(text_parts).strip() or "[No output]"

                tool_results = []
                for tc in tool_calls:
                    result = await _execute_tool(tc.name, tc.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": tc.id, "content": result})
                messages.append({"role": "user", "content": tool_results})

            return "\n".join(text_parts).strip() or "[Max iterations reached]"

    async def research_swarm(self, queries: list[str], shared_context: dict = None) -> str:
        tasks = [{"name": q[:60], "prompt": q} for q in queries]
        results = await self.run(tasks)
        parts = [f"**{r['task']}**\n{r['result']}" for r in results if r["success"]]
        failed = [r["task"] for r in results if not r["success"]]
        if failed:
            parts.append(f"⚠️ Failed: {', '.join(failed)}")
        return "\n\n".join(parts)
