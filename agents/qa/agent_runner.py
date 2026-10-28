from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter

from agents.models import BusMessage, TaskIn, TaskOut
from agents.qa.catalog import CURL_LIVE, OPENRTB_VECTORS, SUITE
from agents.qa.suite import SuiteReport, run_in_process
from agents.runtime import AgentRuntime, bus, build_router
from agents.state import snapshot


class QAAgent(AgentRuntime):
    """QA & Automated Integration Testing — Zero-Error Guardian."""

    def __init__(self) -> None:
        super().__init__(
            name="qa",
            role="QA & Automated Integration Testing Agent",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )

    def suite(self) -> SuiteReport:
        report = run_in_process()
        for case in report.cases:
            if not case.ok:
                self.memory.remember(
                    f"{case.id}: expected {case.expected} got {case.actual}",
                    source=case.layer,
                    resolution="Add/keep a regression test; do not weaken the assertion",
                )
        return report

    def handle(self, task: TaskIn) -> TaskOut:
        task_id = task.task_id or str(uuid4())
        report = self.suite()
        state = snapshot()
        handoffs: list[dict[str, str]] = []
        if not task.context.get("consumed"):
            red_layers = [k for k, v in report.layers.items() if v == "RED"]
            if any(k.startswith("L3") for k in red_layers) or any(
                c.id.startswith("L3") and not c.ok for c in report.cases
            ):
                handoffs.append({"to": "architect", "reason": "bid-path golden rule or latency contract"})
            if any("compliance" in c.id and not c.ok for c in report.cases):
                handoffs.append({"to": "compliance", "reason": "vector verdict drifted"})
            if "L0 Infra" in red_layers or report.live_fleet_ok is False:
                handoffs.append({"to": "devops", "reason": "provision/health for integration tests"})
            handoffs.append({"to": "frontend", "reason": "empty/loading ledger states vs rollup payloads"})

        tool = f"QA {report.verdict}: {report.passed} passed, {report.failed} failed. Layers {report.layers}."
        summary, llm_ok = self.fill_summary(task, tool)
        out = TaskOut(
            ok=(report.verdict == "GREEN") and llm_ok,
            agent=self.name,
            role=self.role,
            task_id=task_id,
            summary=summary,
            actions=[f"{c.id}={'PASS' if c.ok else 'FAIL'} {c.actual}" for c in report.cases if not c.ok]
            or [f"all {report.passed} in-process cases passed"],
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
                payload={**out.model_dump(mode="json"), "report": report.model_dump(mode="json")},
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


runtime = QAAgent()
router: APIRouter = build_router(runtime)


@router.post("/suite", response_model=SuiteReport)
def suite_endpoint() -> SuiteReport:
    return runtime.suite()


@router.get("/catalog")
def catalog() -> dict:
    return {"agent": "qa", "suite": SUITE, "curl_live": CURL_LIVE}


@router.get("/openrtb")
def openrtb_vectors() -> dict:
    return {"agent": "qa", "vectors": OPENRTB_VECTORS, "note": "POST bodies to bidder /openrtb/v2/bid; expect nbr:2 or bid"}
