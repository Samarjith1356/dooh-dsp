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
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10000"))
FLUSH_SECONDS = float(os.getenv("FLUSH_SECONDS", "2"))
DEDUPE_TTL_SECONDS = 48 * 60 * 60

app = FastAPI(title="DOOH ingest")
_lock = threading.Lock()
_buf: list[dict[str, Any]] = []
_duplicates_dropped = 0
_redis = None


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
    imp_id: str = ""
    currency: str = ""
    price_cpm: float = 0
    qty_multiplier: float = 1
    billable_imps: float = 0
    spend_micros: int = 0
    snapshot_id: int = 0


def _redis_client():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis

        _redis = redis.from_url(REDIS_URL, decode_responses=True)
        _redis.ping()
        return _redis
    except Exception as exc:  # noqa: BLE001
        log.warning("redis unavailable for dedupe: %s", exc)
        return None


def _ch_query(sql: str) -> None:
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    resp = httpx.post(url, params={"query": sql}, timeout=10.0)
    resp.raise_for_status()


def migrate_schema() -> None:
    stmts = [
        "ALTER TABLE rtb.events ADD COLUMN IF NOT EXISTS imp_id String",
        "ALTER TABLE rtb.events ADD COLUMN IF NOT EXISTS currency LowCardinality(String)",
    ]
    for attempt in range(1, 8):
        ok = True
        for sql in stmts:
            try:
                _ch_query(sql)
                log.info("migration ok: %s", sql)
            except Exception as exc:  # noqa: BLE001
                ok = False
                log.warning("migration attempt %s failed (%s): %s", attempt, sql, exc)
        if ok:
            return
        time.sleep(min(2 * attempt, 10))


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
        "imp_id": e.get("imp_id") or "",
        "currency": e.get("currency") or "",
        "price_cpm": float(e.get("price_cpm") or 0),
        "qty_multiplier": float(e.get("qty_multiplier") or 1),
        "billable_imps": float(e.get("billable_imps") or 0),
        "spend_micros": int(e.get("spend_micros") or 0),
        "snapshot_id": int(e.get("snapshot_id") or 0),
    }


def _is_duplicate(event_type: str, bid_request_id: str, imp_id: str) -> bool:
    global _duplicates_dropped
    if not event_type or not bid_request_id:
        return False
    r = _redis_client()
    if r is None:
        return False
    key = f"ingest:dedupe:{event_type}:{bid_request_id}:{imp_id}"
    try:
        # SET NX — first writer wins; repeats within TTL are dropped.
        ok = r.set(key, "1", nx=True, ex=DEDUPE_TTL_SECONDS)
        if ok:
            return False
        with _lock:
            _duplicates_dropped += 1
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("dedupe check failed: %s", exc)
        return False


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
        "venue_type,h3,creative_id,bid_request_id,imp_id,currency,price_cpm,qty_multiplier,"
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


def enqueue(raw: dict[str, Any]) -> bool:
    if _is_duplicate(
        str(raw.get("event_type") or ""),
        str(raw.get("bid_request_id") or ""),
        str(raw.get("imp_id") or ""),
    ):
        return False
    with _lock:
        _buf.append(_row(raw))
        n = len(_buf)
    if n >= 1000:
        _flush(force=True)
    return True


@app.post("/events")
def post_event(body: EventIn):
    accepted = enqueue(body.model_dump())
    return {"ok": True, "accepted": accepted}


@app.post("/events/batch")
def post_batch(body: list[EventIn]):
    n = 0
    for item in body:
        if enqueue(item.model_dump()):
            n += 1
    return {"ok": True, "n": n}


@app.get("/health")
def health():
    with _lock:
        buffered = len(_buf)
        dropped = _duplicates_dropped
    return {"ok": True, "buffered": buffered, "duplicates_dropped": dropped}


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
    migrate_schema()
    threading.Thread(target=_flusher, daemon=True).start()
    threading.Thread(target=_kafka_loop, daemon=True).start()
