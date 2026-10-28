from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from agents.config import (
    BIDDER_URL,
    BRAIN_URL,
    CAMPAIGN_API_URL,
    HTTP_TIMEOUT_SEC,
    INGEST_URL,
    REDIS_URL,
)
from agents.models import FleetService, SystemState


def _ping(name: str, url: str) -> FleetService:
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SEC) as client:
            resp = client.get(url)
        ms = round((time.perf_counter() - started) * 1000, 1)
        return FleetService(
            name=name,
            ok=resp.status_code < 400,
            status=resp.status_code,
            latency_ms=ms,
            body=resp.text[:240],
        )
    except Exception as exc:  # noqa: BLE001
        ms = round((time.perf_counter() - started) * 1000, 1)
        return FleetService(name=name, ok=False, status=0, latency_ms=ms, error=str(exc))


def _redis_ok() -> bool:
    try:
        import redis

        r = redis.from_url(REDIS_URL, socket_timeout=1.0)
        return bool(r.ping())
    except Exception:  # noqa: BLE001
        return False


def snapshot() -> SystemState:
    services = [
        _ping("campaign-api", f"{CAMPAIGN_API_URL}/health"),
        _ping("brain", f"{BRAIN_URL}/health"),
        _ping("bidder", f"{BIDDER_URL}/health"),
        _ping("ingest", f"{INGEST_URL}/health"),
    ]
    notes: list[str] = []
    bidder = next(s for s in services if s.name == "bidder")
    if bidder.ok and bidder.latency_ms >= 1:
        notes.append(
            f"bidder /health RTT {bidder.latency_ms}ms is HTTP, not decision time; "
            "decision SLA is X-DSP-Decision-Us < 1000"
        )
    redis_ok = _redis_ok()
    if not redis_ok:
        notes.append("Redis unreachable — Brain snapshots and the agent bus cannot sync")
    return SystemState(
        checked_at=datetime.now(timezone.utc),
        ok=all(s.ok for s in services) and redis_ok,
        services=services,
        redis_ok=redis_ok,
        notes=notes,
    )
