from __future__ import annotations

import json
import logging
import threading
import time

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.compiler import compile_snapshot
from app.config import KAFKA_BROKERS
from app.loader import SessionLocal, load_active_campaigns
from app.pacing import write_budgets
from app.store import current_snapshot, publish_snapshot

log = logging.getLogger("brain")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="DOOH Brain", version="0.1.0")
_epoch = int(time.time())


def compile_now() -> dict:
    global _epoch
    db: Session = SessionLocal()
    try:
        views = load_active_campaigns(db)
    finally:
        db.close()
    _epoch += 1
    snap = compile_snapshot(views, _epoch)
    write_budgets(views)
    publish_snapshot(snap)
    return {"snapshot_id": snap.snapshot_id, "campaigns": len(snap.campaigns)}


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
    return {"ok": True}


def _kafka_loop() -> None:
    try:
        from kafka import KafkaConsumer
    except Exception:
        return
    while True:
        try:
            consumer = KafkaConsumer(
                "campaign.plan.updated",
                "pacing.spend.tick",
                bootstrap_servers=KAFKA_BROKERS.split(","),
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="brain",
                auto_offset_reset="latest",
            )
            for _msg in consumer:
                compile_now()
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


@app.on_event("startup")
def startup():
    threading.Thread(target=_kafka_loop, daemon=True).start()
    threading.Thread(target=_pacing_loop, daemon=True).start()
    try:
        compile_now()
    except Exception as exc:  # noqa: BLE001
        log.warning("initial compile skipped: %s", exc)
