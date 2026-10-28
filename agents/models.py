from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal[
    "architect",
    "compliance",
    "devops",
    "analytics",
    "frontend",
    "qa",
    "product",
    "orchestrator",
]


class TaskIn(BaseModel):
    task_id: str = Field(default="", description="Caller correlation id")
    objective: str
    context: dict[str, Any] = Field(default_factory=dict)
    from_agent: AgentName | str = "orchestrator"
    reply_to: AgentName | str | None = None
    priority: int = 100


class ErrorRecord(BaseModel):
    fingerprint: str
    message: str
    source: str
    seen_at: datetime
    count: int = 1
    resolution: str = ""


class FleetService(BaseModel):
    name: str
    ok: bool
    status: int = 0
    latency_ms: float = 0
    error: str | None = None
    body: str = ""


class SystemState(BaseModel):
    checked_at: datetime
    ok: bool
    services: list[FleetService]
    redis_ok: bool = False
    notes: list[str] = Field(default_factory=list)


class TaskOut(BaseModel):
    ok: bool
    agent: str
    role: str
    task_id: str
    summary: str
    actions: list[str] = Field(default_factory=list)
    handoffs: list[dict[str, str]] = Field(default_factory=list)
    avoided_mistakes: list[str] = Field(default_factory=list)
    system_ok: bool
    received_at: datetime


class BusMessage(BaseModel):
    kind: Literal["task", "handoff", "audit", "error", "health"] = "task"
    from_agent: str
    to_agent: str = "*"
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
