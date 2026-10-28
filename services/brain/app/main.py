from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.compiler import compile_snapshot, consult_memory
from app.config import KAFKA_BROKERS
from app.loader import SessionLocal, load_active_campaigns
from app.pacing import write_budgets
from app.store import current_snapshot, publish_snapshot
from memory.observe import observe_fleet
from memory.store import ensure_schema, metrics, recall, remember, seed_architecture

log = logging.getLogger("brain")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="DOOH Brain", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_epoch = int(time.time())
_last_compile_fp = ""


class MemoryIn(BaseModel):
    kind: str
    source: str
    title: str
    body: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


def compile_now() -> dict:
    global _epoch, _last_compile_fp
    db: Session = SessionLocal()
    try:
        views = load_active_campaigns(db)
    finally:
        db.close()
    mem = recall(
        query="pacing budget cap compliance compile campaign",
        kinds=["architecture", "campaign", "audit", "decision"],
        limit=16,
    )
    views, mem_notes = consult_memory(views, mem)
    _epoch += 1
    snap = compile_snapshot(views, _epoch)
    write_budgets(views)
    publish_snapshot(snap)
    fp = f"{snap.snapshot_id}:{sorted(c.id for c in snap.campaigns)}"
    if fp != _last_compile_fp:
        remember(
            kind="compile",
            source="brain.compiler",
            title=f"Compiled snapshot {snap.snapshot_id}",
            body=f"campaigns={len(snap.campaigns)} notes={'; '.join(mem_notes) or 'none'}",
            payload={
                "snapshot_id": snap.snapshot_id,
                "campaign_ids": [c.id for c in snap.campaigns],
                "memory_notes": mem_notes,
            },
        )
        _last_compile_fp = fp
    return {
        "snapshot_id": snap.snapshot_id,
        "campaigns": len(snap.campaigns),
        "memory_notes": mem_notes,
        "memory_chunks_consulted": len(mem),
    }


@app.post("/compile")
def compile_endpoint():
    return compile_now()


@app.get("/snapshot/{snapshot_id}")
def get_snapshot(snapshot_id: int):
    data = current_snapshot()
    if not data or int(data.get("snapshot_id", 0)) != snapshot_id:
        return current_snapshot()
    return data


@app.get("/health")
def health():
    return {"ok": True, "memory": metrics().get("chunks", 0)}


@app.post("/v1/memory")
def memory_write(body: MemoryIn):
    return remember(kind=body.kind, source=body.source, title=body.title, body=body.body, payload=body.payload)


@app.get("/v1/memory")
def memory_read(q: str = "", kind: str = "", limit: int = 20):
    kinds = [kind] if kind else None
    return {"ok": True, "items": recall(query=q, kinds=kinds, limit=min(limit, 50))}


@app.get("/v1/memory/state")
def memory_state():
    return metrics()


def _kafka_loop() -> None:
    try:
        from kafka import KafkaConsumer
    except Exception:
        return
    topics = (
        "campaign.plan.updated",
        "pacing.spend.tick",
        "agents.events",
        "rules.compiled",
    )
    while True:
        try:
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=KAFKA_BROKERS.split(","),
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="brain-memory",
                auto_offset_reset="latest",
            )
            for msg in consumer:
                topic = msg.topic
                val = msg.value if isinstance(msg.value, dict) else {}
                if topic in {"campaign.plan.updated", "pacing.spend.tick"}:
                    remember(
                        kind="campaign" if topic.startswith("campaign") else "audit",
                        source=f"kafka.{topic}",
                        title=topic,
                        body=json.dumps(val, default=str)[:2000],
                        payload=val if isinstance(val, dict) else {},
                    )
                    compile_now()
                elif topic == "agents.events":
                    kind = str(val.get("kind") or "audit")
                    if kind == "health":
                        continue
                    remember(
                        kind="chat" if kind in {"audit", "handoff"} else ("error" if kind == "error" else "audit"),
                        source=f"agent.{val.get('from_agent') or 'bus'}",
                        title=f"{kind} {val.get('from_agent')}→{val.get('to_agent')}",
                        body=json.dumps(val.get("payload") or val, default=str)[:2000],
                        payload=val if isinstance(val, dict) else {},
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("kafka loop: %s", exc)
            time.sleep(3)


def _pacing_loop() -> None:
    while True:
        time.sleep(15)
        try:
            compile_now()
        except Exception as exc:  # noqa: BLE001
            log.warning("pacing compile: %s", exc)


def _observe_loop() -> None:
    while True:
        time.sleep(45)
        try:
            observe_fleet()
        except Exception as exc:  # noqa: BLE001
            log.warning("memory observe: %s", exc)


@app.on_event("startup")
def startup():
    ensure_schema()
    seed_architecture()
    threading.Thread(target=_kafka_loop, daemon=True).start()
    threading.Thread(target=_pacing_loop, daemon=True).start()
    threading.Thread(target=_observe_loop, daemon=True).start()
    try:
        compile_now()
    except Exception as exc:  # noqa: BLE001
        log.warning("initial compile skipped: %s", exc)
    seed_architecture()
    try:
        observe_fleet()
    except Exception as exc:  # noqa: BLE001
        log.debug("initial observe skipped: %s", exc)
