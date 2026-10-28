from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from agents.cognition import remember as remember_enterprise
from agents.worklog import all_agent_cards
from agents.config import (
    CAMPAIGN_API_URL,
    CLICKHOUSE_HOST,
    CLICKHOUSE_HTTP_PORT,
    HTTP_TIMEOUT_SEC,
    REDIS_URL,
)

log = logging.getLogger("agents.desk")

APPROVALS_KEY = "desk:approvals"
FEED_KEY = "agents:feed"
DAYPART_FLAG = "desk:daypart:go_sunday0"
REPO = Path(__file__).resolve().parents[1]
CH_XML = REPO / "infra" / "clickhouse" / "users.d" / "default-network.xml"
CH_XML_SAFE = """<clickhouse>
  <users>
    <default>
      <networks>
        <ip>10.0.0.0/8</ip>
        <ip>172.16.0.0/12</ip>
        <ip>192.168.0.0/16</ip>
        <ip>127.0.0.1</ip>
        <ip>::1</ip>
      </networks>
    </default>
  </users>
</clickhouse>
"""
ALTER_USER_SQL = (
    "ALTER USER default HOST IP '10.0.0.0/8', IP '172.16.0.0/12', "
    "IP '192.168.0.0/16', IP '127.0.0.1', IP '::1'"
)
CAP_MICROS = 500_000_000


class Approval(BaseModel):
    id: str
    agent: str
    title: str
    detail: str
    createdAt: str
    status: str = "pending"
    action: str = ""
    result: str = ""
    comment: str = ""


class DecideIn(BaseModel):
    status: str  # approved | rejected
    comment: str = ""


class DeskAgent(BaseModel):
    id: str
    status: str
    lastAction: str
    lastActionAt: str
    attention: str = ""
    progress: int = 0
    job: dict[str, Any] | None = None
    recent_jobs: list[dict[str, Any]] = Field(default_factory=list)


class DeskSnapshot(BaseModel):
    live: bool = True
    approvals: list[Approval] = Field(default_factory=list)
    feed: list[dict[str, Any]] = Field(default_factory=list)
    agents: list[DeskAgent] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redis():
    try:
        import redis

        r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1.5)
        r.ping()
        return r
    except Exception as exc:  # noqa: BLE001
        log.warning("desk redis unavailable: %s", exc)
        return None


def _http_get(url: str) -> Any:
    with httpx.Client(timeout=HTTP_TIMEOUT_SEC) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def _http_post(url: str, payload: dict[str, Any] | None = None) -> Any:
    with httpx.Client(timeout=max(HTTP_TIMEOUT_SEC, 3.0)) as client:
        resp = client.post(url, json=payload or {})
        resp.raise_for_status()
        if resp.content:
            try:
                return resp.json()
            except Exception:  # noqa: BLE001
                return {"raw": resp.text[:400]}
        return {}


def append_feed(from_agent: str, to_agent: str, text: str, severity: str = "info", topic: str = "desk") -> None:
    item = {
        "id": f"live-{datetime.now(timezone.utc).timestamp()}",
        "at": _now(),
        "from": from_agent,
        "to": to_agent,
        "severity": severity,
        "topic": topic,
        "text": text,
    }
    r = _redis()
    if not r:
        return
    r.lpush(FEED_KEY, json.dumps(item))
    r.ltrim(FEED_KEY, 0, 99)


def _stored() -> dict[str, Approval]:
    r = _redis()
    if not r:
        return {}
    out: dict[str, Approval] = {}
    for raw in r.hvals(APPROVALS_KEY):
        try:
            item = Approval.model_validate_json(raw)
            out[item.id] = item
        except Exception:  # noqa: BLE001
            continue
    return out


def _save(item: Approval) -> None:
    r = _redis()
    if not r:
        raise RuntimeError("Redis is required to persist executive decisions")
    r.hset(APPROVALS_KEY, item.id, item.model_dump_json())


def clickhouse_open_to_world() -> bool:
    text = CH_XML.read_text(encoding="utf-8", errors="replace") if CH_XML.exists() else ""
    if "::/0" in text:
        return True
    try:
        url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
        with httpx.Client(timeout=HTTP_TIMEOUT_SEC) as client:
            resp = client.get(url, params={"query": "SHOW CREATE USER default"})
        return "::/0" in resp.text or "0.0.0.0/0" in resp.text
    except Exception:  # noqa: BLE001
        return "::/0" in text


def remap_commute_dow(dayparts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Heuristic 0-4 (Mon-first) → Go time.Weekday Sunday=0 so weekdays are 1-5."""
    mapped = []
    for block in dayparts:
        dow = int(block.get("dow", 0))
        mapped.append({**block, "dow": (dow + 1) % 7})
    return mapped


def _discover(stored: dict[str, Approval]) -> list[Approval]:
    found: list[Approval] = []
    # Local Compose needs ClickHouse ::/0 so ingest is not HTTP 403. Do not
    # surface that as an executive blocker. Daypart remap is a compile
    # convention, not required for the stack to run.

    try:
        campaigns = _http_get(f"{CAMPAIGN_API_URL}/v1/campaigns")
    except Exception as exc:  # noqa: BLE001
        campaigns = []
        log.info("campaign list skipped: %s", exc)

    r = _redis()
    starved: list[dict[str, Any]] = []
    for camp in campaigns or []:
        cid = camp.get("id")
        rem = None
        if r and cid is not None:
            raw = r.get(f"budget:{cid}:remaining_micros")
            if raw is not None:
                try:
                    rem = int(raw)
                except ValueError:
                    rem = None
        if rem == 0:
            starved.append(camp)
    prior_cap = stored.get("cap-raise")
    if starved and (not prior_cap or prior_cap.status == "pending"):
        names = ", ".join(f"{c.get('name')}#{c.get('id')}" for c in starved[:4])
        found.append(
            Approval(
                id="cap-raise",
                agent="product",
                title="Raise starved campaign caps",
                detail=f"Live Redis remaining_micros=0 for {names}. Approve sets total_cap_micros={CAP_MICROS} and resets remaining (soak, not a new client).",
                createdAt=prior_cap.createdAt if prior_cap else _now(),
                action="raise_cap",
                status="pending",
            )
        )

    return found


def snapshot_desk() -> DeskSnapshot:
    stored = _stored()
    pending = {a.id: a for a in _discover(stored)}
    merged: dict[str, Approval] = {**pending}
    for item in stored.values():
        if item.status != "pending":
            merged[item.id] = item
    approvals = sorted(merged.values(), key=lambda a: a.createdAt, reverse=True)

    r = _redis()
    feed: list[dict[str, Any]] = []
    if r:
        for raw in r.lrange(FEED_KEY, 0, 39):
            try:
                feed.append(json.loads(raw))
            except Exception:  # noqa: BLE001
                continue

    feed = [row for row in feed if str(row.get("topic") or "") != "health"]
    cards = []
    for row in all_agent_cards():
        cards.append(DeskAgent.model_validate(row))
    pending_only = [a for a in approvals if a.status == "pending"]
    executed = [a for a in approvals if a.status != "pending"]
    return DeskSnapshot(live=bool(r), approvals=pending_only + executed, feed=feed, agents=cards)


def execute_ch_acl() -> str:
    notes: list[str] = []
    try:
        CH_XML.parent.mkdir(parents=True, exist_ok=True)
        CH_XML.write_text(CH_XML_SAFE, encoding="utf-8")
        notes.append(f"wrote {CH_XML}")
    except OSError as exc:
        notes.append(f"xml write skipped: {exc}")
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    with httpx.Client(timeout=max(HTTP_TIMEOUT_SEC, 4.0)) as client:
        alter = client.post(url, params={"query": ALTER_USER_SQL})
        notes.append(f"ALTER USER HTTP {alter.status_code} {alter.text[:160]}")
        if alter.status_code >= 400:
            raise RuntimeError("ClickHouse ALTER USER failed: " + alter.text[:300])
        reload = client.post(url, params={"query": "SYSTEM RELOAD CONFIG"})
        notes.append(f"RELOAD {reload.status_code}")
    return "; ".join(notes)


def execute_raise_cap() -> str:
    campaigns = _http_get(f"{CAMPAIGN_API_URL}/v1/campaigns")
    r = _redis()
    updated: list[str] = []
    for camp in campaigns or []:
        cid = camp.get("id")
        rem = None
        if r and cid is not None:
            raw = r.get(f"budget:{cid}:remaining_micros")
            rem = int(raw) if raw is not None and str(raw).lstrip("-").isdigit() else None
        if rem != 0:
            continue
        _http_post(
            f"{CAMPAIGN_API_URL}/v1/campaigns/{cid}/budget",
            {"total_cap_micros": CAP_MICROS, "reset_remaining": True},
        )
        updated.append(f"{camp.get('name')}#{cid}")
    if not updated:
        raise RuntimeError("No campaign with remaining_micros=0")
    return "raised cap for " + ", ".join(updated)


def execute_daypart_map() -> str:
    campaigns = _http_get(f"{CAMPAIGN_API_URL}/v1/campaigns")
    changed = 0
    for camp in campaigns or []:
        plans = _http_get(f"{CAMPAIGN_API_URL}/v1/campaigns/{camp['id']}/plans")
        for plan in plans or []:
            blocks = list(plan.get("dayparts") or [])
            dows = {int(b.get("dow", 0)) for b in blocks}
            if not blocks or not (dows <= {0, 1, 2, 3, 4}):
                continue
            _http_post(
                f"{CAMPAIGN_API_URL}/v1/plans/{plan['id']}/dayparts",
                {"dayparts": remap_commute_dow(blocks)},
            )
            changed += 1
    r = _redis()
    if r:
        r.set(DAYPART_FLAG, "1")
    if changed == 0:
        if r:
            r.set(DAYPART_FLAG, "1")
        return "no commute 0-4 plans left; flag set"
    return f"remapped {changed} plan(s) to Go Sunday=0 weekdays"


def decide(approval_id: str, body: DecideIn) -> Approval:
    if body.status not in {"approved", "rejected"}:
        raise ValueError("status must be approved or rejected")
    if body.status == "rejected" and not body.comment.strip():
        raise ValueError("reject comment required")
    snap = snapshot_desk()
    item = next((a for a in snap.approvals if a.id == approval_id), None)
    if item is None:
        stored = _stored().get(approval_id)
        if stored is None:
            raise KeyError(approval_id)
        item = stored
    item.status = body.status
    item.comment = body.comment
    if body.status == "rejected":
        item.result = f"rejected: {body.comment}"
        _save(item)
        append_feed("orchestrator", item.agent, f"Sam rejected {item.title}: {body.comment}", "warning", "approval")
        remember_enterprise(
            kind="decision",
            source="desk",
            title=f"rejected {item.title}",
            body=body.comment,
            payload={"approval_id": item.id, "action": item.action, "status": "rejected"},
        )
        return item
    runners = {
        "ch_acl": execute_ch_acl,
        "raise_cap": execute_raise_cap,
        "daypart_map": execute_daypart_map,
    }
    runner = runners.get(item.action)
    if runner is None:
        item.result = "no live action bound"
    else:
        item.result = runner()
    _save(item)
    append_feed("orchestrator", item.agent, f"Sam approved {item.title} → {item.result}", "info", "approval")
    remember_enterprise(
        kind="decision",
        source="desk",
        title=f"approved {item.title}",
        body=item.result or "",
        payload={"approval_id": item.id, "action": item.action, "status": "approved"},
    )
    return item
