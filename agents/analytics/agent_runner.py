from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from agents.analytics.engine import InsightPack, SQL_CATALOG, pack
from agents.models import BusMessage, TaskIn, TaskOut
from agents.runtime import AgentRuntime, bus, build_router
from agents.state import snapshot


class AnalyticsAgent(AgentRuntime):
    """Data & Analytics Intelligence — ClickHouse rollups, pacing, dashboard copy."""

    def __init__(self) -> None:
        super().__init__(
            name="analytics",
            role="Data & Analytics Intelligence Agent",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )

    def insights(self, advertiser_id: int, campaign_id: int | None = None, cap_micros: int | None = None) -> InsightPack:
        pack_ = pack(advertiser_id, campaign_id, cap_micros)
        if not pack_.ch_ok:
            self.memory.remember(
                pack_.error or "clickhouse query failed",
                source="analytics.clickhouse",
                resolution="Check ingest 403 / HOST LOCAL; never query CH from the bidder",
            )
        if "integrity_mismatch" in pack_.alerts:
            self.memory.remember(
                "hourly MV vs rtb.events spend/imps mismatch",
                source="analytics.integrity",
                resolution="Wait for async_insert merge; do not double-count qty.multiplier",
            )
        return pack_

    def handle(self, task: TaskIn) -> TaskOut:
        task_id = task.task_id or str(uuid4())
        ctx = task.context
        advertiser_id = int(ctx.get("advertiser_id") or 1)
        campaign_id = ctx.get("campaign_id")
        campaign_id = int(campaign_id) if campaign_id not in (None, "", 0) else None
        cap = ctx.get("cap_micros")
        cap = int(cap) if cap not in (None, "") else None
        result = self.insights(advertiser_id, campaign_id, cap)
        state = snapshot()
        handoffs: list[dict[str, str]] = []
        if not ctx.get("consumed"):
            handoffs.append({"to": "product", "reason": "dashboard / Studio performance copy"})
            if not result.ch_ok or "integrity_mismatch" in result.alerts:
                handoffs.append({"to": "devops", "reason": "ClickHouse ingest or ACL; buffer/async_insert"})
            if result.kpis.paced_out:
                handoffs.append({"to": "product", "reason": "campaign paced out — remaining 0 is correct"})
            if result.kpis.billable_imps and result.kpis.avg_cpm == 0:
                handoffs.append({"to": "architect", "reason": "CPM formula or event_type filter anomaly"})

        tool = result.insight
        summary, llm_ok = self.fill_summary(task, tool)
        out = TaskOut(
            ok=result.ch_ok and llm_ok,
            agent=self.name,
            role=self.role,
            task_id=task_id,
            summary=summary,
            actions=[
                f"imps={result.kpis.billable_imps} spend_micros={result.kpis.spend_micros} cpm={result.kpis.avg_cpm}",
                f"integrity={'ok' if result.integrity.ok else 'MISMATCH'} {result.integrity.note}",
                *result.alerts,
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
                payload={**out.model_dump(mode="json"), "insights": result.model_dump(mode="json")},
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


runtime = AnalyticsAgent()
router: APIRouter = build_router(runtime)


@router.get("/insights", response_model=InsightPack)
def insights_endpoint(advertiser_id: int = 1, campaign_id: int | None = None, cap_micros: int | None = None) -> InsightPack:
    return runtime.insights(advertiser_id, campaign_id, cap_micros)


@router.get("/sql")
def sql_catalog() -> dict:
    return {"agent": "analytics", "catalog": SQL_CATALOG, "qty_rule": "billable_imps already includes qty.multiplier"}


@router.post("/integrity", response_model=InsightPack)
def integrity_endpoint(advertiser_id: int = 1, campaign_id: int | None = None) -> InsightPack:
    if advertiser_id <= 0:
        raise HTTPException(400, "advertiser_id required")
    return runtime.insights(advertiser_id, campaign_id)
