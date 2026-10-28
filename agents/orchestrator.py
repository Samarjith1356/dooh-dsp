from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents import ROSTER
from agents.analytics.agent_runner import runtime as analytics_runtime
from agents.analytics.agent_runner import router as analytics_router
from agents.architect.agent_runner import runtime as architect_runtime
from agents.architect.agent_runner import router as architect_router
from agents.compliance.agent_runner import runtime as compliance_runtime
from agents.compliance.agent_runner import router as compliance_router
from agents.config import AGENT_LISTEN, HEALTH_INTERVAL_SEC
from agents.devops.agent_runner import runtime as devops_runtime
from agents.devops.agent_runner import router as devops_router
from agents.frontend.agent_runner import runtime as frontend_runtime
from agents.frontend.agent_runner import router as frontend_router
from agents.models import BusMessage, TaskIn
from agents.product.agent_runner import runtime as product_runtime
from agents.product.agent_runner import router as product_router
from agents.qa.agent_runner import runtime as qa_runtime
from agents.qa.agent_runner import router as qa_router
from agents.runtime import bus as shared_bus
from agents.state import snapshot

log = logging.getLogger("agents.orchestrator")
logging.basicConfig(level=logging.INFO)

RUNTIMES = {
    "architect": architect_runtime,
    "compliance": compliance_runtime,
    "devops": devops_runtime,
    "analytics": analytics_runtime,
    "frontend": frontend_runtime,
    "qa": qa_runtime,
    "product": product_runtime,
}

app = FastAPI(
    title="DOOH DSP Enterprise Agent Workforce",
    version="1.0.0",
    description="Control-plane agents. Never mounted on the Go bid path.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for router in (
    architect_router,
    compliance_router,
    devops_router,
    analytics_router,
    frontend_router,
    qa_router,
    product_router,
):
    app.include_router(router, prefix="/v1/agents")


@app.get("/health")
def health() -> dict:
    state = snapshot()
    return {
        "ok": True,
        "plane": "control",
        "agents": list(ROSTER),
        "fleet": state.model_dump(mode="json"),
    }


@app.post("/v1/agents/dispatch")
def dispatch(body: TaskIn) -> dict:
    """Route a task to one agent (from_agent/reply_to) or fan out a broadcast."""
    target = str(body.reply_to or body.context.get("agent") or "architect")
    if target == "*" or target == "all":
        results = {name: rt.handle(body).model_dump(mode="json") for name, rt in RUNTIMES.items()}
        return {"ok": True, "broadcast": True, "results": results}
    runtime = RUNTIMES.get(target)
    if runtime is None:
        runtime = architect_runtime
        target = "architect"
    result = runtime.handle(body)
    return {"ok": result.ok, "agent": target, "result": result.model_dump(mode="json")}


def _on_bus(msg: BusMessage) -> None:
    if (
        msg.kind == "handoff"
        and msg.to_agent in RUNTIMES
        and msg.from_agent != msg.to_agent
        and not msg.payload.get("consumed")
    ):
        hop = TaskIn(
            task_id=str(msg.payload.get("task_id") or ""),
            objective=f"Handoff: {msg.payload.get('reason')}: {msg.payload.get('objective')}",
            context={**msg.payload, "consumed": True},
            from_agent=msg.from_agent,
            reply_to=msg.to_agent,
        )
        RUNTIMES[msg.to_agent].handle(hop)
        return
    if msg.kind == "error" and msg.from_agent != "qa":
        qa_runtime.record_error(
            message=str(msg.payload.get("message") or "peer error"),
            source=f"bus.{msg.from_agent}",
            resolution=str(msg.payload.get("resolution") or ""),
        )


def _health_loop(stop: threading.Event) -> None:
    while not stop.is_set():
        state = snapshot()
        shared_bus.publish(
            BusMessage(
                kind="health",
                from_agent="orchestrator",
                to_agent="*",
                payload=state.model_dump(mode="json"),
            )
        )
        log.info("health audit ok=%s at %s", state.ok, datetime.now(timezone.utc).isoformat())
        stop.wait(HEALTH_INTERVAL_SEC)


_stop = threading.Event()


@app.on_event("startup")
def startup() -> None:
    channels = ["agents.bus", "agents.bus.errors", "agents.bus.health"] + [f"agents.bus.{name}" for name in ROSTER]
    shared_bus.subscribe(_on_bus, channels=channels)
    threading.Thread(target=_health_loop, args=(_stop,), name="agent-health", daemon=True).start()
    log.info("agent orchestrator listening; roster=%s", ",".join(ROSTER))


@app.on_event("shutdown")
def shutdown() -> None:
    _stop.set()
    shared_bus.close()


def main() -> None:
    import uvicorn

    host, _, port = AGENT_LISTEN.partition(":")
    uvicorn.run("agents.orchestrator:app", host=host or "0.0.0.0", port=int(port or 8091), reload=False)


if __name__ == "__main__":
    main()
