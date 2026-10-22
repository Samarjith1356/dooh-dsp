from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

log = logging.getLogger("ingest")
logging.basicConfig(level=logging.INFO)

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_HTTP_PORT = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:19092")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10000"))
FLUSH_SECONDS = float(os.getenv("FLUSH_SECONDS", "2"))

app = FastAPI(title="DOOH ingest")
_lock = threading.Lock()
_buf: list[dict[str, Any]] = []


class EventIn(BaseModel):
    event_type: str
    event_time: str = ""
    advertiser_id: int = 0
    campaign_id: int = 0
    ssp: str = "simulator"
    country: str = ""
    venue_type: str = ""
    h3: int = 0
    creative_id: int = 0
    bid_request_id: str = ""
    price_cpm: float = 0
    qty_multiplier: float = 1
    billable_imps: float = 0
    spend_micros: int = 0
    snapshot_id: int = 0


def _row(e: dict[str, Any]) -> dict[str, Any]:
    ts = e.get("event_time") or datetime.now(timezone.utc).isoformat()
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)
    return {
        "event_date": dt.date().isoformat(),
        "event_time": dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "event_type": e.get("event_type") or "bid",
        "advertiser_id": int(e.get("advertiser_id") or 0),
        "campaign_id": int(e.get("campaign_id") or 0),
        "ssp": e.get("ssp") or "",
        "country": e.get("country") or "",
        "venue_type": e.get("venue_type") or "",
        "h3": int(e.get("h3") or 0),
        "creative_id": int(e.get("creative_id") or 0),
        "bid_request_id": e.get("bid_request_id") or "",
        "price_cpm": float(e.get("price_cpm") or 0),
        "qty_multiplier": float(e.get("qty_multiplier") or 1),
        "billable_imps": float(e.get("billable_imps") or 0),
        "spend_micros": int(e.get("spend_micros") or 0),
        "snapshot_id": int(e.get("snapshot_id") or 0),
    }


def _flush(force: bool = False) -> None:
    with _lock:
        if not _buf:
            return
        if not force and len(_buf) < max(1, min(BATCH_SIZE, 1000)):
            return
        batch = list(_buf)
        _buf.clear()
    payload = "\n".join(json.dumps(r) for r in batch)
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    query = (
        "INSERT INTO rtb.events "
        "(event_date,event_time,event_type,advertiser_id,campaign_id,ssp,country,"
        "venue_type,h3,creative_id,bid_request_id,price_cpm,qty_multiplier,"
        "billable_imps,spend_micros,snapshot_id) FORMAT JSONEachRow"
    )
    try:
        resp = httpx.post(
            url,
            params={"query": query, "async_insert": 1, "wait_for_async_insert": 0},
            content=payload.encode("utf-8"),
            timeout=10.0,
        )
        resp.raise_for_status()
        log.info("inserted %s rows", len(batch))
    except Exception as exc:  # noqa: BLE001
        log.warning("clickhouse insert failed (%s rows): %s", len(batch), exc)
        with _lock:
            _buf[:0] = batch


def _flusher() -> None:
    while True:
        time.sleep(FLUSH_SECONDS)
        _flush(force=True)


def enqueue(raw: dict[str, Any]) -> None:
    with _lock:
        _buf.append(_row(raw))
        n = len(_buf)
    if n >= 1000:
        _flush(force=True)


@app.post("/events")
def post_event(body: EventIn):
    enqueue(body.model_dump())
    return {"ok": True}


@app.post("/events/batch")
def post_batch(body: list[EventIn]):
    for item in body:
        enqueue(item.model_dump())
    return {"ok": True, "n": len(body)}


@app.get("/health")
def health():
    return {"ok": True, "buffered": len(_buf)}


def _kafka_loop() -> None:
    try:
        from kafka import KafkaConsumer
    except Exception:
        return
    while True:
        try:
            consumer = KafkaConsumer(
                "rtb.bid_log",
                bootstrap_servers=KAFKA_BROKERS.split(","),
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="ingest",
                auto_offset_reset="latest",
            )
            for msg in consumer:
                if isinstance(msg.value, dict):
                    enqueue(msg.value)
        except Exception as exc:  # noqa: BLE001
            log.warning("kafka ingest: %s", exc)
            time.sleep(3)


@app.on_event("startup")
def startup():
    threading.Thread(target=_flusher, daemon=True).start()
    threading.Thread(target=_kafka_loop, daemon=True).start()
