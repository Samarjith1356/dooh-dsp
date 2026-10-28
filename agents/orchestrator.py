from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents import ROSTER
from agents.analytics.agent_runner import runtime as analytics_runtime
from agents.analytics.agent_runner import router as analytics_router
from agents.architect.agent_runner import runtime as architect_runtime
from agents.architect.agent_runner import router as architect_router
from agents.compliance.agent_runner import runtime as compliance_runtime
from agents.compliance.agent_runner import router as compliance_router
from agents.config import AGENT_LISTEN, HEALTH_INTERVAL_SEC
from agents.cognition import remember as remember_enterprise, state as memory_state
from agents.worklog import begin_turn, finish_turn, is_idle_command, maybe_idle, maybe_idle_all, thread, thread_bundle
from agents.llm import status as llm_status
from agents.desk import DecideIn, decide as desk_decide, snapshot_desk
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
        "llm": llm_status(),
        "memory": memory_state(),
    }


@app.get("/v1/desk")
def desk() -> dict:
    maybe_idle_all()
    snap = snapshot_desk().model_dump(mode="json")
    snap["memory"] = memory_state()
    return snap


@app.get("/v1/desk/agents/{agent}/thread")
def desk_thread(agent: str) -> dict:
    maybe_idle(agent)
    if agent not in RUNTIMES:
        raise HTTPException(404, f"unknown agent {agent}")
    return thread_bundle(agent)


@app.post("/v1/desk/approvals/{approval_id}/decide")
def desk_approval(approval_id: str, body: DecideIn) -> dict:
    try:
        item = desk_decide(approval_id, body)
    except KeyError as exc:
        raise HTTPException(404, f"unknown approval {exc}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc
    return item.model_dump(mode="json")


@app.post("/v1/agents/dispatch")
def dispatch(body: TaskIn) -> dict:
    """Route a task to one agent (from_agent/reply_to) or fan out a broadcast."""
    target = str(body.reply_to or body.context.get("agent") or "architect")
    if target == "*" or target == "all":
        results = {name: rt.handle(body).model_dump(mode="json") for name, rt in RUNTIMES.items()}
        remember_enterprise(
            kind="chat",
            source="desk.broadcast",
            title=body.objective[:180] or "broadcast",
            body="fan-out to all seven agents",
            payload={"broadcast": True},
        )
        return {"ok": True, "broadcast": True, "results": results}
    runtime = RUNTIMES.get(target)
    if runtime is None:
        runtime = architect_runtime
        target = "architect"
    if is_idle_command(body.objective):
        begin_turn(target, body.objective)
        bundle = thread_bundle(target)
        return {"ok": True, "agent": target, "result": {"ok": True, "summary": "Back to idle.", "agent": target}, "thread": bundle}
    begin_turn(target, body.objective)
    prior = [{"role": m.get("role"), "text": m.get("text")} for m in thread(target)[:-1]]
    ctx = dict(body.context or {})
    ctx["history"] = prior or ctx.get("history") or []
    body = body.model_copy(update={"context": ctx})
    result = runtime.handle(body)
    finish_turn(target, result.summary or "")
    remember_enterprise(
        kind="chat",
        source=f"agent.{target}",
        title=body.objective[:180] or f"dispatch {target}",
        body=(result.summary or "")[:4000],
        payload={"agent": target, "task_id": result.task_id, "ok": result.ok},
    )
    return {"ok": result.ok, "agent": target, "result": result.model_dump(mode="json"), "thread": thread_bundle(target)}


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
    if msg.kind in {"audit", "error"} and msg.kind != "health":
        remember_enterprise(
            kind="error" if msg.kind == "error" else "audit",
            source=f"agent.{msg.from_agent}",
            title=f"{msg.kind} {msg.from_agent}→{msg.to_agent}",
            body=str(msg.payload)[:2000],
            payload={"kind": msg.kind, "from": msg.from_agent, "to": msg.to_agent},
        )
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
