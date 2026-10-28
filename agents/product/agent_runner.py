from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agents.analytics.engine import pack as analytics_pack
from agents.models import BusMessage, TaskIn, TaskOut
from agents.product.planner import Orchestration, orchestrate
from agents.runtime import AgentRuntime, bus, build_router
from agents.state import snapshot


class ParseIn(BaseModel):
    message: str
    advertiser_id: int = 1
    campaign_id: int | None = None
    geofence_ids: list[int] = Field(default_factory=list)


class ProductAgent(AgentRuntime):
    """Product & Client Campaign Agent — goals to PlanIn JSON, never live bid rules."""

    def __init__(self) -> None:
        super().__init__(
            name="product",
            role="Product & Client Campaign Agent",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )

    def parse(self, body: ParseIn) -> Orchestration:
        insight = None
        intent_msg = body.message
        if intent_msg.lower().startswith("performance") or "how is" in intent_msg.lower():
            try:
                insight = analytics_pack(body.advertiser_id, body.campaign_id).insight
            except Exception as exc:  # noqa: BLE001
                insight = f"Analytics unavailable ({exc}). Try again when ClickHouse/ingest are up."
                self.memory.remember(str(exc)[:200], source="product.analytics", resolution="Handoff DevOps; do not invent spend")
        result = orchestrate(
            body.message,
            advertiser_id=body.advertiser_id,
            campaign_id=body.campaign_id,
            geofence_ids=body.geofence_ids or None,
            insight=insight,
        )
        if result.plan and result.compliance and result.compliance.verdict == "REJECTED":
            self.memory.remember(
                f"blocked goal: {body.message[:120]}",
                source="product.compliance",
                resolution="Do not present approval CTA; ask for a compliant rewrite",
            )
        return result

    def handle(self, task: TaskIn) -> TaskOut:
        task_id = task.task_id or str(uuid4())
        body = ParseIn(
            message=task.objective,
            advertiser_id=int(task.context.get("advertiser_id") or 1),
            campaign_id=task.context.get("campaign_id"),
            geofence_ids=list(task.context.get("geofence_ids") or []),
        )
        result = self.parse(body)
        state = snapshot()
        handoffs: list[dict[str, str]] = []
        if not task.context.get("consumed"):
            if result.intent == "plan":
                handoffs.append({"to": "compliance", "reason": "plan+copy already screened; keep fingerprint"})
                handoffs.append({"to": "frontend", "reason": "Studio split-screen plan preview + approval gate"})
            if result.intent == "performance":
                handoffs.append({"to": "analytics", "reason": "hourly/spend copy for dashboard"})
            if result.compliance and result.compliance.verdict == "REJECTED":
                handoffs.append({"to": "compliance", "reason": "client goal blocked — do not compile"})
            handoffs.append({"to": "architect", "reason": "PlanIn schema / daypart dow mapping"})

        tool = result.reply
        summary, llm_ok = self.fill_summary(task, tool)
        out = TaskOut(
            ok=(result.compliance.verdict != "REJECTED" if result.compliance else True) and llm_ok,
            agent=self.name,
            role=self.role,
            task_id=task_id,
            summary=summary,
            actions=[
                f"intent={result.intent}",
                f"next_state={result.next_state}",
                f"can_present_approval={result.can_present_approval}",
                *(result.parse_notes),
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
                to_agent=task.reply_to or "frontend",
                payload={**out.model_dump(mode="json"), "orchestration": result.model_dump(mode="json")},
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


runtime = ProductAgent()
router: APIRouter = build_router(runtime)


@router.post("/parse", response_model=Orchestration)
def parse_endpoint(body: ParseIn) -> Orchestration:
    return runtime.parse(body)
