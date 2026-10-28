from __future__ import annotations

import logging

import httpx

from app.config import BIDDER_URL, CLICKHOUSE_HOST, CLICKHOUSE_HTTP_PORT, INGEST_URL
from memory.store import recall, remember

log = logging.getLogger("brain.memory.observe")


def _last_fingerprint(kind: str, source: str) -> str:
    rows = recall(kinds=[kind], limit=8)
    for r in rows:
        if r.get("source") == source:
            return str((r.get("payload") or {}).get("fingerprint") or "")
    return ""


def observe_fleet() -> None:
    """Sample bidder /health and ingest — never from inside the Go process."""
    try:
        with httpx.Client(timeout=1.5) as client:
            bidder = client.get(f"{BIDDER_URL}/health")
            body = bidder.json() if bidder.headers.get("content-type", "").startswith("application/json") else {}
            us = int(body.get("avg_decision_us") or 0)
            fp = f"bidder:{bidder.status_code}:{us}:{body.get('bids')}"
            if fp != _last_fingerprint("latency", "bidder.health"):
                kind = "latency" if bidder.status_code < 400 else "error"
                remember(
                    kind=kind,
                    source="bidder.health",
                    title=f"Bidder decision {us}µs" if bidder.status_code < 400 else "Bidder health failed",
                    body=f"status={bidder.status_code} avg_decision_us={us} bids={body.get('bids')} max={body.get('max_decision_us')}",
                    payload={"avg_decision_us": us, "ok": bidder.status_code < 400, "fingerprint": fp},
                )
                if us > 1000:
                    remember(
                        kind="audit",
                        source="bidder.health",
                        title="Decision SLA excursion",
                        body=f"avg_decision_us={us} exceeded 1000µs budget. Do not add IO to the bidder.",
                        payload={"avg_decision_us": us, "fingerprint": fp + ":sla"},
                    )
            ingest = client.get(f"{INGEST_URL}/health")
            ib = ingest.json() if ingest.content else {}
            ifp = f"ingest:{ingest.status_code}:{ib.get('buffered')}"
            if ifp != _last_fingerprint("latency", "ingest.health"):
                remember(
                    kind="latency" if ingest.status_code < 400 else "error",
                    source="ingest.health",
                    title="Ingest buffer",
                    body=f"status={ingest.status_code} buffered={ib.get('buffered')}",
                    payload={"buffered": ib.get("buffered"), "fingerprint": ifp},
                )
    except Exception as exc:  # noqa: BLE001
        log.debug("observe fleet: %s", exc)
    _observe_clickhouse()


def _observe_clickhouse() -> None:
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    q = "SELECT count() AS n, countIf(event_type='error') AS errors FROM rtb.events WHERE event_time > now() - INTERVAL 15 MINUTE FORMAT JSON"
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.post(url, params={"query": q})
        if resp.status_code >= 400:
            return
        data = resp.json()
        row = (data.get("data") or [{}])[0]
        n = int(row.get("n") or 0)
        errors = int(row.get("errors") or 0)
        fp = f"ch:{n}:{errors}"
        if fp != _last_fingerprint("audit", "clickhouse.events"):
            remember(
                kind="audit" if errors else "latency",
                source="clickhouse.events",
                title=f"Ingest window events={n} errors={errors}",
                body="Control-plane sample of rtb.events. Bidder does not query ClickHouse.",
                payload={"events_15m": n, "errors_15m": errors, "fingerprint": fp},
            )
    except Exception as exc:  # noqa: BLE001
        log.debug("observe clickhouse: %s", exc)
