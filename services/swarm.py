"""
Swarm — Parallel subagent coordination.
Spawn multiple Claude agents for independent tasks, merge results.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable
from config import ANTHROPIC_API_KEY, MODEL


@dataclass
class AgentTask:
    task_id:     str
    description: str
    prompt:      str
    status:      str = "pending"
    result:      Optional[str] = None
    error:       Optional[str] = None


class SwarmCoordinator:
    def __init__(self, client=None, max_concurrent: int = 4, model: str = None):
        import anthropic
        self.client         = client or anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.max_concurrent = max_concurrent
        self.model          = model or MODEL
        self._semaphore     = asyncio.Semaphore(max_concurrent)

    async def run_parallel(self, tasks: list[AgentTask], shared_context: dict = None) -> list[AgentTask]:
        await asyncio.gather(*[self._run_task(t, shared_context or {}) for t in tasks])
        return tasks

    async def _run_task(self, task: AgentTask, context: dict):
        async with self._semaphore:
            task.status = "running"
            try:
                ctx_str = f"\n\nSHARED CONTEXT: {context}" if context else ""
                resp = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model, max_tokens=1000,
                    system="You are a focused subagent. Complete your specific task concisely.",
                    messages=[{"role": "user", "content": task.prompt + ctx_str}],
                )
                task.result = resp.content[0].text
                task.status = "done"
            except Exception as e:
                task.status = "failed"
                task.error  = str(e)

    def summarize(self, tasks: list[AgentTask]) -> str:
        parts = [f"**{t.description}**\n{t.result}" for t in tasks if t.status == "done"]
        failed = [t.description for t in tasks if t.status == "failed"]
        if failed:
            parts.append(f"⚠️ Failed: {', '.join(failed)}")
        return "\n\n".join(parts)

    async def research_swarm(self, queries: list[str], shared_context: dict = None) -> str:
        tasks = [
            AgentTask(
                task_id=str(uuid.uuid4())[:8],
                description=q[:60],
                prompt=q,
            )
            for q in queries
        ]
        await self.run_parallel(tasks, shared_context)
        return self.summarize(tasks)
