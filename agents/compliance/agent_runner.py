from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from agents.compliance.scanner import QA_VECTORS, AuditRequest, AuditResult, audit, from_task
from agents.models import BusMessage, TaskIn, TaskOut
from agents.runtime import AgentRuntime, bus, build_router
from agents.state import snapshot


class ComplianceAgent(AgentRuntime):
    """AdTech Compliance & Regulatory Agent — ASA/CAP and IE safety guard."""

    def __init__(self) -> None:
        super().__init__(
            name="compliance",
            role="AdTech Compliance & Regulatory Agent",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )

    def audit(self, req: AuditRequest) -> AuditResult:
        result = audit(req)
        if result.verdict != "APPROVED":
            self.memory.remember(
                f"{result.verdict}: " + ", ".join(f.rule_id for f in result.findings),
                source="compliance.audit",
                resolution="; ".join(result.alternatives[:2]),
            )
        return result

    def handle(self, task: TaskIn) -> TaskOut:
        task_id = task.task_id or str(uuid4())
        state = snapshot()
        result = self.audit(from_task(task.objective, task.context))
        avoided = self.memory.reminders()
        handoffs: list[dict[str, str]] = []
        if not task.context.get("consumed"):
            if result.verdict != "APPROVED":
                handoffs.append(
                    {
                        "to": "product",
                        "reason": f"{result.verdict}: rewrite copy/asset before approval",
                    }
                )
                handoffs.append({"to": "qa", "reason": "add/keep rejection vector for this claim class"})
            if any(f.rule_id.startswith("cap-") and "filename" in task.context for f in result.findings):
                handoffs.append(
                    {"to": "architect", "reason": "extend creative.validate_asset beyond WxH/codec for this policy"}
                )

        tool = (
            f"Verdict {result.verdict} for '{task.objective[:140]}'. "
            f"{len(result.findings)} finding(s). Markets: {', '.join(result.markets_reviewed) or 'GB/IE'}."
        )
        summary, llm_ok = self.fill_summary(task, tool)
        out = TaskOut(
            ok=(result.verdict != "REJECTED") and llm_ok,
            agent=self.name,
            role=self.role,
            task_id=task_id,
            summary=summary,
            actions=[
                f"verdict={result.verdict}",
                *[f"{f.rule_id}: {f.citation} (evidence '{f.evidence}')" for f in result.findings],
                *result.alternatives,
            ],
            handoffs=handoffs,
            avoided_mistakes=avoided,
            system_ok=state.ok,
            received_at=datetime.now(timezone.utc),
        )
        bus.publish(
            BusMessage(
                kind="audit",
                from_agent=self.name,
                to_agent=task.reply_to or "product",
                payload={**out.model_dump(mode="json"), "compliance": result.model_dump(mode="json")},
            )
        )
        for hop in handoffs:
            bus.publish(
                BusMessage(
                    kind="handoff",
                    from_agent=self.name,
                    to_agent=hop["to"],
                    payload={
                        "task_id": task_id,
                        "reason": hop["reason"],
                        "objective": task.objective,
                        "verdict": result.verdict,
                    },
                )
            )
        return out


runtime = ComplianceAgent()
router: APIRouter = build_router(runtime)


@router.post("/audit", response_model=AuditResult)
def audit_endpoint(body: AuditRequest) -> AuditResult:
    return runtime.audit(body)


@router.get("/vectors")
def vectors() -> dict:
    """QA test vectors: non-compliant assets that must not reach Brain compile."""
    return {"agent": "compliance", "vectors": QA_VECTORS}


@router.post("/breach")
def publisher_breach(message: str, resolution: str = "", source: str = "publisher") -> dict:
    """Record a publisher/network rejection so the same oversight is never repeated."""
    if not message.strip():
        raise HTTPException(400, "message is required")
    runtime.record_error(message, source, resolution)
    return {"ok": True, "reminders": runtime.memory.reminders()}
