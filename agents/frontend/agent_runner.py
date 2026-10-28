from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter

from agents.frontend.auditor import CHECKLIST, UxAudit, audit
from agents.models import BusMessage, TaskIn, TaskOut
from agents.runtime import AgentRuntime, bus, build_router
from agents.state import snapshot


class FrontendAgent(AgentRuntime):
    """Frontend & Enterprise UX — Next.js control center, RBAC honesty, HITL studio."""

    def __init__(self) -> None:
        super().__init__(
            name="frontend",
            role="Frontend & Enterprise UX Agent",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )

    def audit(self) -> UxAudit:
        result = audit()
        for f in result.findings:
            if f.severity == "critical":
                self.memory.remember(f.evidence, source=f.id, resolution=f.remediation)
        return result

    def handle(self, task: TaskIn) -> TaskOut:
        task_id = task.task_id or str(uuid4())
        result = self.audit()
        state = snapshot()
        handoffs: list[dict[str, str]] = []
        if not task.context.get("consumed"):
            handoffs.append({"to": "product", "reason": "Studio chat/plan-preview vs approval gates"})
            handoffs.append({"to": "analytics", "reason": "KPI/hourly/events payload shape for charts"})
            if any(f.id == "error-boundary" for f in result.findings):
                handoffs.append({"to": "qa", "reason": "add error.tsx / empty-state route tests"})
            if any(f.id == "rbac-client-only" for f in result.findings):
                handoffs.append({"to": "architect", "reason": "UI RBAC is not server tenancy"})
            if any(f.id == "typescript-pin" for f in result.findings):
                handoffs.append({"to": "devops", "reason": "web Docker build TS pin"})

        tool = f"UX verdict {result.verdict}. Pillars {result.pillars}. RBAC server={result.rbac_server_enforced}."
        summary, llm_ok = self.fill_summary(task, tool)
        out = TaskOut(
            ok=(result.verdict != "BLOCKED") and llm_ok,
            agent=self.name,
            role=self.role,
            task_id=task_id,
            summary=summary,
            actions=[
                f"verdict={result.verdict}",
                *[f"{f.severity}:{f.id} {f.evidence}" for f in result.findings if f.severity != "pass"],
            ],
            handoffs=handoffs,
            avoided_mistakes=self.memory.reminders(),
            system_ok=state.ok,
            received_at=datetime.now(timezone.utc),
        )
        bus.publish(
            BusMessage(
                kind="audit",
                from_agent=self.name,
                to_agent=task.reply_to or "product",
                payload={**out.model_dump(mode="json"), "ux": result.model_dump(mode="json")},
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


runtime = FrontendAgent()
router: APIRouter = build_router(runtime)


@router.post("/audit", response_model=UxAudit)
def audit_endpoint() -> UxAudit:
    return runtime.audit()


@router.get("/checklist")
def checklist() -> dict:
    return {"agent": "frontend", "pillars": list(CHECKLIST), "verify": "browser: /, /inventory, /studio, /analytics"}
