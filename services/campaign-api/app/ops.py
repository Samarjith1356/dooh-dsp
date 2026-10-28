from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import BIDDER_URL, BRAIN_URL, INGEST_URL


def _ping(name: str, url: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(url)
        ms = round((time.perf_counter() - started) * 1000, 1)
        return {"name": name, "ok": resp.status_code < 400, "status": resp.status_code, "latency_ms": ms, "body": resp.text[:200]}
    except Exception as exc:  # noqa: BLE001
        ms = round((time.perf_counter() - started) * 1000, 1)
        return {"name": name, "ok": False, "status": 0, "latency_ms": ms, "error": str(exc)}


def fleet_health() -> dict[str, Any]:
    services = [
        _ping("brain", f"{BRAIN_URL}/health"),
        _ping("bidder", f"{BIDDER_URL}/health"),
        _ping("ingest", f"{INGEST_URL}/health"),
    ]
    return {"ok": all(s["ok"] for s in services), "services": services}
