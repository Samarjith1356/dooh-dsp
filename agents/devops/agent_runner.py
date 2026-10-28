from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter

from agents.devops.auditor import CHAOS_PLAYBOOK, InfraAudit, audit
from agents.models import BusMessage, TaskIn, TaskOut
from agents.runtime import AgentRuntime, bus, build_router
from agents.state import snapshot


class DevOpsAgent(AgentRuntime):
    """Site Reliability & Infrastructure — zero-trust Compose, Redis sync, bid-path isolation."""

    def __init__(self) -> None:
        super().__init__(
            name="devops",
            role="Site Reliability & Infrastructure (DevOps) Agent",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )

    def audit(self, live: bool = True) -> InfraAudit:
        result = audit(live=live)
        for f in result.findings:
            if f.severity == "critical":
                self.memory.remember(f.evidence, source=f.id, resolution=f.remediation)
        return result

    def handle(self, task: TaskIn) -> TaskOut:
        task_id = task.task_id or str(uuid4())
        live = bool(task.context.get("live", True))
        result = self.audit(live=live)
        state = snapshot()
        handoffs: list[dict[str, str]] = []
        if not task.context.get("consumed"):
            if not result.bidder_isolation_ok:
                handoffs.append({"to": "architect", "reason": "bidder isolation violated — datastore on hot path"})
                handoffs.append({"to": "qa", "reason": "fail CI if bidder imports CH/PG"})
            if any(f.id == "ch-wildcard" for f in result.findings):
                handoffs.append({"to": "analytics", "reason": "ClickHouse ::/0 is dev-only; coordinate prod ACL + ingest user"})
                handoffs.append({"to": "qa", "reason": "staging ACL change will 403 ingest unless tests use Docker DNS"})
            if result.redis_snapshot_ok is False:
                handoffs.append({"to": "architect", "reason": "Redis rules:current/snapshot desync"})
            if any(f.area == "latency" and f.severity in {"warn", "critical"} for f in result.findings):
                handoffs.append({"to": "architect", "reason": "decision_us regression or bidder down"})

        crit = [f.id for f in result.findings if f.severity == "critical"]
        tool = (
            f"Infra verdict {result.verdict}. "
            f"isolation={'ok' if result.bidder_isolation_ok else 'BROKEN'}. "
            f"critical={crit or 'none'}."
        )
        summary, llm_ok = self.fill_summary(task, tool)
        out = TaskOut(
            ok=(result.verdict != "HARDENING_REQUIRED") and llm_ok,
            agent=self.name,
            role=self.role,
            task_id=task_id,
            summary=summary,
            actions=[
                f"verdict={result.verdict}",
                *[f"{f.severity}:{f.id} {f.evidence}" for f in result.findings if f.severity != "pass"],
                *[f.remediation for f in result.findings if f.severity == "critical"],
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
                to_agent=task.reply_to or "architect",
                payload={**out.model_dump(mode="json"), "infra": result.model_dump(mode="json")},
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


runtime = DevOpsAgent()
router: APIRouter = build_router(runtime)


@router.post("/audit", response_model=InfraAudit)
def audit_endpoint(live: bool = True) -> InfraAudit:
    return runtime.audit(live=live)


@router.get("/policies/clickhouse")
def clickhouse_policy() -> dict:
    path = Path(__file__).with_name("policies") / "clickhouse-default-prod.xml"
    return {
        "path": "agents/devops/policies/clickhouse-default-prod.xml",
        "replaces": "infra/clickhouse/users.d/default-network.xml",
        "xml": path.read_text(encoding="utf-8") if path.exists() else "",
        "tradeoff": "Ingest from unknown hosts 403s. Requires CLICKHOUSE_PASSWORD and Docker RFC1918.",
    }


@router.get("/chaos")
def chaos() -> dict:
    return {
        "agent": "devops",
        "note": "Plans only — do not run qps_500 against a live client cap.",
        "playbook": CHAOS_PLAYBOOK,
    }
