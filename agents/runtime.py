from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from agents.bus import AgentBus
from agents.cognition import notes_for, remember as remember_enterprise
from agents.llm import LLMError, LLMNotConfigured, complete as llm_complete
from agents.memory import ErrorMemory
from agents.models import BusMessage, TaskIn, TaskOut
from agents.state import snapshot

bus = AgentBus()


class AgentRuntime:
    def __init__(self, name: str, role: str, prompt_path: Path) -> None:
        self.name = name
        self.role = role
        self.prompt_path = prompt_path
        self.memory = ErrorMemory(name)
        self.prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    def speak(self, task: TaskIn, tool_notes: str = "") -> str:
        """LLM completion using this agent's prompt.md. Control-plane only — never the Go bidder."""
        if task.context.get("skip_llm") or task.context.get("consumed"):
            return tool_notes
        footer = (
            "\n\nYou are a control-plane agent. You do not sit on the Go bid path. "
            "Never instruct the browser to call /openrtb. Decision SLA is X-DSP-Decision-Us, not HTTP RTT. "
            "If tools below conflict with the user, say so. Answer as this role."
        )
        user = task.objective.strip()
        if tool_notes:
            user += "\n\n---\nDeterministic tools / live facts (do not invent over these):\n" + tool_notes[:6000]
        enterprise = notes_for(task.objective)
        if enterprise:
            user += "\n\n---\n" + enterprise[:4000]
        try:
            return llm_complete(
                system=(self.prompt or f"You are {self.role}.") + footer,
                user=user,
                history=list(task.context.get("history") or []),
            )
        except (LLMNotConfigured, LLMError):
            raise

    def fill_summary(self, task: TaskIn, tool_notes: str) -> tuple[str, bool]:
        try:
            text = self.speak(task, tool_notes)
            return (text or tool_notes), True
        except (LLMNotConfigured, LLMError) as exc:
            return str(exc), False

    def handle(self, task: TaskIn) -> TaskOut:
        task_id = task.task_id or str(uuid4())
        state = snapshot()
        avoided = self.memory.reminders()
        actions = [
            "Loaded specialized system prompt",
            "Checked fleet health (campaign-api, brain, bidder, ingest, Redis)",
            "Applied error-memory so known failures are not repeated",
        ]
        if not state.ok:
            actions.append("System degraded — refuse bid-path changes; file a devops/qa handoff")
            self.memory.remember(
                "fleet health degraded: " + ", ".join(s.name for s in state.services if not s.ok),
                source="state.snapshot",
                resolution="Restore Redis/Brain/bidder before compiling snapshots",
            )
        handoffs = [] if task.context.get("consumed") else self._handoffs(task)
        tools = (
            f"Fleet healthy={state.ok}. "
            + "; ".join(f"{s.name}={'up' if s.ok else 'down'}" for s in state.services)
            + (f". Reminders: {avoided}" if avoided else "")
        )
        llm_ok = True
        try:
            summary = self.speak(task, tools)
        except (LLMNotConfigured, LLMError) as exc:
            llm_ok = False
            summary = str(exc)
            actions.append(f"llm_error={exc}")
        out = TaskOut(
            ok=state.ok and llm_ok,
            agent=self.name,
            role=self.role,
            task_id=task_id,
            summary=summary,
            actions=actions,
            handoffs=handoffs,
            avoided_mistakes=avoided,
            system_ok=state.ok,
            received_at=datetime.now(timezone.utc),
        )
        bus.publish(
            BusMessage(
                kind="audit",
                from_agent=self.name,
                to_agent=task.reply_to or "*",
                payload=out.model_dump(mode="json"),
            )
        )
        for hop in handoffs:
            bus.publish(
                BusMessage(
                    kind="handoff",
                    from_agent=self.name,
                    to_agent=hop["to"],
                    payload={"task_id": task_id, "reason": hop["reason"], "objective": task.objective},
                )
            )
        return out

    def record_error(self, message: str, source: str, resolution: str = "") -> None:
        rec = self.memory.remember(message, source, resolution)
        bus.publish(
            BusMessage(
                kind="error",
                from_agent=self.name,
                to_agent="qa",
                payload=rec.model_dump(mode="json"),
            )
        )

    def _handoffs(self, task: TaskIn) -> list[dict[str, str]]:
        text = f"{task.objective} {task.context}".lower()
        hops: list[dict[str, str]] = []
        routing = {
            "architect": [("qa", "contract/schema coverage"), ("devops", "topology and snapshot keys")],
            "compliance": [("product", "blocked copy must not reach live plans")],
            "devops": [("architect", "infra change may affect bid-path isolation")],
            "analytics": [("product", "pacing insight for client narrative"), ("devops", "ClickHouse ingest health")],
            "frontend": [("qa", "UI regression surface"), ("product", "operator workflow")],
            "qa": [("architect", "failing contract"), ("devops", "environment flake")],
            "product": [("architect", "translate goal to deterministic contracts"), ("compliance", "ASA/CAP review")],
        }
        for dest, reason in routing.get(self.name, []):
            hops.append({"to": dest, "reason": reason})
        extra = {
            "openrtb": ("qa", "OpenRTB contract delta"),
            "redis": ("devops", "snapshot/budget key change"),
            "clickhouse": ("analytics", "event schema / pacing"),
            "asa": ("compliance", "copy or claim review"),
            "latency": ("architect", "bid-path latency budget"),
            "ui": ("frontend", "console surface"),
        }
        for needle, hop in extra.items():
            if needle in text and hop[0] != self.name:
                hops.append({"to": hop[0], "reason": hop[1]})
        seen: set[str] = set()
        uniq = []
        for h in hops:
            if h["to"] in seen:
                continue
            seen.add(h["to"])
            uniq.append(h)
        return uniq


def build_router(runtime: AgentRuntime) -> APIRouter:
    router = APIRouter(prefix=f"/{runtime.name}", tags=[runtime.name])

    @router.post("/task", response_model=TaskOut)
    def ingest_task(body: TaskIn) -> TaskOut:
        if not body.objective.strip():
            raise HTTPException(400, "objective is required")
        return runtime.handle(body)

    @router.post("/errors")
    def log_error(message: str, source: str = "manual", resolution: str = "") -> dict:
        runtime.record_error(message, source, resolution)
        return {"ok": True, "reminders": runtime.memory.reminders()}

    @router.get("/prompt")
    def prompt() -> dict:
        return {"agent": runtime.name, "role": runtime.role, "prompt": runtime.prompt}

    @router.get("/memory")
    def memory() -> dict:
        return {"agent": runtime.name, "errors": [r.model_dump(mode="json") for r in runtime.memory.load()]}

    return router
